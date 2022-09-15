import math
import sys
import os
import re
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Iterable, Optional, Tuple

from bs4 import BeautifulSoup
from markdownify import markdownify
from pytz import timezone as tz, UnknownTimeZoneError
from tzlocal import get_localzone

import logging

log = logging.getLogger()


@dataclass
class JourneyEntry:
    id: str
    path: str
    date_journal: int
    text: str
    type: str
    lat: float
    lon: float
    timezone: str
    address: str
    tags: List[str]
    photos: List[str]


@dataclass
class ValidatedEntry:
    foreign_id: str
    source_path: str
    text: str
    tags: List[str]
    photos: List[str]
    lat: Optional[float]
    lon: Optional[float]
    timestamp: str
    timezone: str


@dataclass
class ImportOneResult:
    image_count: int = 0
    tag_count: int = 0
    word_count: int = 0


@dataclass
class ImportManyResult:
    failed_entry_paths: List[str]
    skipped_entry_paths: List[str]
    skipped_attachment_paths: List[str]
    attempted_entry_count: int = 0
    total_entry_count: int = 0


class Importer:
    def __init__(self, src_directory, target_journal_name):
        self.src_directory = src_directory
        self.target_journal_name = target_journal_name
        self.data = None

    def run(self):
        self.data = ImportManyResult([], [], [])
        raw_entries = self.load_journey_entries(self.src_directory)
        valid_entries = self.validate_journey_entries(raw_entries)
        imported_entries = self.import_journey_entries(valid_entries)
        self.print_result(imported_entries)

    def load_journey_entries(self, root) -> Iterable[JourneyEntry]:
        for file in self.iter_journey_files(root):
            yield self.load_entry(file)

    @staticmethod
    def iter_journey_files(root) -> Iterable[str]:
        p = Path(root)
        for file in p.rglob("*.json"):
            yield file

    def load_entry(self, file) -> JourneyEntry:
        with open(file) as f:
            text = f.read()
            body = json.loads(text)
            entry = self.extract_entry_from_body(body, file)
            return entry

    @staticmethod
    def extract_entry_from_body(body, path) -> JourneyEntry:
        return JourneyEntry(
            id=body["id"],
            date_journal=body["date_journal"],
            text=body["text"],
            lon=body["lon"],
            lat=body["lat"],
            tags=body["tags"],
            photos=body["photos"],
            address=body["address"],
            type=body["type"],
            timezone=body["timezone"],
            path=path,
        )

    @staticmethod
    def determine_attachment_type(path: str) -> str:
        """
        Journey's entries have a list of file paths called `photos`, but this list can contain more than just photos.
        It's actually a list of files paths to any artifacts that were attached to entries, including photos (.jpg),
        but also videos (.mp4), and audio (.mp3).

        This function determines the type of attachment based on the file extension of the provided path.
        """
        result: str = (
            "photo"  # Assume anything that's not mp4 or mp3 is a photo (e.g., png, jpg)
        )
        if path.endswith("mp4"):
            result = "video"
        elif path.endswith("mp3"):
            result = "audio"
        return result

    def validate_journey_entries(
        self, raw_entries: Iterable[JourneyEntry]
    ) -> Iterable[ValidatedEntry]:
        for raw in raw_entries:
            entry = self.validate_journey_entry(raw)
            if entry:
                yield entry

    def validate_journey_entry(self, raw: JourneyEntry) -> Optional[ValidatedEntry]:
        log.info("Validating Journey entry {}".format(raw.id))
        foreign_id = raw.id
        source_path = raw.path

        timezone = ""
        if raw.timezone:
            try:
                timezone = tz(raw.timezone).zone
            except UnknownTimeZoneError:
                log.warning("Timezone is invalid: {}".format(raw.timezone))
        if not timezone:
            timezone = get_localzone().zone

        timestamp = ""
        timestamp_format = "%Y-%m-%d %I:%M:%S %p"
        if raw.date_journal is not None:
            try:
                dt = datetime.fromtimestamp(raw.date_journal / 1000)
                timestamp = dt.strftime(timestamp_format)
            except (OverflowError, ValueError, OSError):
                log.warning("Entry's timestamp is invalid: {}".format(raw.date_journal))
        if not timestamp:
            dt = datetime.now(tz(timezone))
            timestamp = dt.strftime(timestamp_format)

        photos = []
        if len(raw.photos) > 0:
            for path in raw.photos:
                abs_path = os.path.abspath(os.path.join(self.src_directory, path))
                if os.path.exists(abs_path) and os.path.isfile(abs_path):
                    photos.append(abs_path)
                else:
                    artifact_type: str = self.determine_attachment_type(path)
                    log.warning(
                        "Journey export is missing {} attachment: Can't find {}".format(
                            artifact_type, abs_path
                        )
                    )
                    self.data.skipped_attachment_paths.append(source_path)

        tags = []
        if len(raw.tags) > 0:
            escaped_tags = map(self.escape_tag, raw.tags)
            tags.extend(escaped_tags)

        lat = None
        lon = None
        if raw.lat is not None and raw.lon is not None:
            is_lat_valid = (
                math.isfinite(raw.lat)
                and math.fabs(raw.lat) <= 90
                and raw.lat != sys.float_info.max
            )
            is_lon_valid = (
                math.isfinite(raw.lon)
                and math.fabs(raw.lon) <= 180
                and raw.lon != sys.float_info.max
            )
            if is_lat_valid and is_lon_valid:
                lat = raw.lat
                lon = raw.lon
            elif raw.lat == sys.float_info.max and raw.lon == sys.float_info.max:
                log.debug(
                    "Journey doesn't have location information for entry {}".format(
                        raw.id
                    )
                )
            else:
                log.warning(
                    "Entry's location coordinates are invalid: {} {} for entry {}".format(
                        raw.lat, raw.lon, raw.id
                    )
                )

        skip = False
        text = self.convert_html_to_markdown(raw.text)
        if not text:
            log.warning("Entry has no text: id={}".format(raw.id))
        if not text and len(photos) == 0:
            log.warning(
                "Entry has no text and no photos, skipping: id={}".format(raw.id)
            )
            skip = True
        if text.find("dayone-moment:") != -1:
            log.warning(
                "Skipped previously-exported Day One entry: id={}".format(raw.id)
            )
            skip = True

        if not skip:
            return ValidatedEntry(
                foreign_id=foreign_id,
                source_path=source_path,
                text=text,
                photos=photos,
                tags=tags,
                lat=lat,
                lon=lon,
                timestamp=timestamp,
                timezone=timezone,
            )
        else:
            self.data.skipped_entry_paths.append(source_path)
            return None

    @staticmethod
    def escape_tag(raw):
        tag = re.sub(r"\s+", r"\\\g<0>", raw)
        return tag

    @staticmethod
    def convert_html_to_markdown(original_text):
        soup = BeautifulSoup(original_text, "html5lib")
        is_html = bool(soup.find())  # true if at least one HTML element can be found
        if is_html:
            return markdownify(original_text)
        else:
            return original_text

    def import_journey_entries(self, entries: Iterable[ValidatedEntry]):
        flat_entries = list(entries)
        self.data.total_entry_count = len(flat_entries)
        for entry in flat_entries:
            id, err = self.import_one_entry(entry)
            self.data.attempted_entry_count += 1
            if not err:
                prefix = "[{}/{}]".format(
                    self.data.attempted_entry_count, self.data.total_entry_count
                )
                data = []
                if entry.text:
                    data.append("{} words".format(len(entry.text.split())))
                if len(entry.tags):
                    data.append("{} tags".format(len(entry.tags)))
                if len(entry.photos):
                    data.append("{} attachments".format(len(entry.photos)))
                if len(data):
                    log.info(
                        "{} Entry added to Day One {} -> {}: {}".format(
                            prefix, entry.foreign_id, id, ", ".join(data)
                        )
                    )
                else:
                    log.info(
                        "{} Entry added to Day One {} -> {}".format(
                            prefix, entry.foreign_id, id
                        )
                    )
                yield entry
            else:
                self.data.failed_entry_paths.append(entry.source_path)
                log.error("{}".format(err))

    def import_one_entry(
        self, entry: ValidatedEntry
    ) -> Tuple[Optional[str], Optional[str]]:  # id, err
        args = self.build_dayone_args(entry)
        log.debug(args)
        try:
            p = subprocess.run(args, input=entry.text, text=True, capture_output=True)
        except OSError as e:
            log.error(
                "Can't access your Day One journal. Make sure you installed Day One command-line tools."
            )
            raise
        if p.returncode == 0:
            id = self.parse_id_from_output(p.stdout)
            return id, None
        else:
            err = p.stderr
            return None, err

    def build_dayone_args(self, entry: ValidatedEntry):
        args = ["dayone2", "-j", self.target_journal_name]
        args.extend(["-d", entry.timestamp])
        args.extend(["-z", entry.timezone])
        if len(entry.tags) > 0:
            args.extend(["-t", *entry.tags])
        if len(entry.photos) > 0:
            args.extend(["-p", *entry.photos])
        if entry.lat and entry.lon:
            args.extend(["--coordinate", str(entry.lat), str(entry.lon)])
        args.extend(["--", "new"])
        return args

    @staticmethod
    def parse_id_from_output(output):
        # E.g.: "Created new entry with uuid: CB17A357BED34F6D838410CA96C7D9D1"
        m = re.search(r"([A-F0-9]+)\s*$", output)
        if m:
            id = m.group(1)
            return id
        else:
            return ""

    def report_missing_attachments(self):
        with open("./missing-attachments-report.json", "w") as f:
            # TODO: map to object with human readable dates.
            # TODO: compose recovery instructions.
            log.debug("Writing skipped attachment data.")
            json.dump(self.data.skipped_attachment_paths, f)

    def print_result(self, imported_entries: Iterable[ValidatedEntry]):
        succeeded_count = len(list(imported_entries))
        self.print_paths("SKIPPED ATTACHMENTS", self.data.skipped_attachment_paths)
        self.print_paths("SKIPPED ENTRIES", self.data.skipped_entry_paths)
        self.print_paths("FAILED ENTRIES", self.data.failed_entry_paths)
        skipped_count = len(self.data.skipped_entry_paths)
        failed_count = len(self.data.failed_entry_paths)
        log.info(
            "{} succeeded, {} failed, {} skipped".format(
                succeeded_count, failed_count, skipped_count
            )
        )
        if self.data.skipped_attachment_paths:
            log.warning("Your Journey export was missing some attachments.")
            log.info(
                "Writing missing attachment report to missing-attachments-report.json..."
            )
            log.warning(
                "See TODO for a list of attachments and instructions on how to recover them."
            )

    @staticmethod
    def print_paths(prefix, paths):
        for path in paths:
            log.info("{}: {}".format(prefix, path))
