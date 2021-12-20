import math
import os
import re
import sys
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Iterable, Optional, Tuple

from bs4 import BeautifulSoup
from pytz import timezone as tz, UnknownTimeZoneError
from tzlocal import get_localzone
from markdownify import markdownify


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
    failed_paths: List[str]
    skipped_paths: List[str]
    attempted_count: int = 0
    total_count: int = 0


def parse_args():
    args = sys.argv
    if len(args) < 3:
        raise RuntimeError('missing [dest_journal_name] and/or [src_directory] arguments')
    dest_journal_name = sys.argv[1]
    src_directory = os.path.expanduser(sys.argv[2])
    if not os.path.exists(src_directory):
        raise RuntimeError('directory is missing or invalid')
    return dest_journal_name, src_directory


class Importer:
    def __init__(self, src_directory, target_journal_name, debug=False):
        self.src_directory = src_directory
        self.target_journal_name = target_journal_name
        self.debug = debug
        self.data = None

    def run(self):
        self.data = ImportManyResult([], [])
        raw_entries = self.load_journey_entries(self.src_directory)
        valid_entries = self.validate_journey_entries(raw_entries)
        imported_entries = self.import_entries(valid_entries)
        self.print_result(imported_entries)

    def load_journey_entries(self, root) -> Iterable[JourneyEntry]:
        for file in self.iter_journey_files(root):
            yield self.load_entry(file)

    def iter_journey_files(self, root) -> Iterable[str]:
        p = Path(root)
        for file in p.rglob('*.json'):
            yield file

    def load_entry(self, file) -> JourneyEntry:
        with open(file) as f:
            text = f.read()
            body = json.loads(text)
            entry = self.extract_entry_from_body(body, file)
            return entry

    def extract_entry_from_body(self, body, path) -> JourneyEntry:
        return JourneyEntry(id=body['id'], date_journal=body['date_journal'], text=body['text'], lon=body['lon'],
                            lat=body['lat'], tags=body['tags'], photos=body['photos'], address=body['address'],
                            type=body['type'], timezone=body['timezone'], path=path)

    def validate_journey_entries(self, raw_entries: Iterable[JourneyEntry]) -> Iterable[ValidatedEntry]:
        for raw in raw_entries:
            entry = self.build_valid_entry(raw)
            if entry:
                yield entry

    def build_valid_entry(self, raw: JourneyEntry) -> Optional[ValidatedEntry]:
        foreign_id = raw.id
        source_path = raw.path

        timezone = ''
        if raw.timezone:
            try:
                timezone = tz(raw.timezone).zone
            except UnknownTimeZoneError:
                print('WARNING: timezone is invalid: {}'.format(raw.timezone))
        if not timezone:
            timezone = get_localzone().zone

        timestamp = ''
        timestamp_format = '%Y-%m-%d %I:%M:%S %p'
        if raw.date_journal is not None:
            try:
                dt = datetime.fromtimestamp(raw.date_journal / 1000)
                timestamp = dt.strftime(timestamp_format)
            except (OverflowError, ValueError, OSError):
                print('WARNING: timestamp is invalid: {}'.format(raw.date_journal))
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
                    print('WARNING: photo path is invalid: {}'.format(abs_path))

        tags = []
        if len(raw.tags) > 0:
            escaped_tags = map(self.escape_tag, raw.tags)
            tags.extend(escaped_tags)

        lat = None
        lon = None
        if raw.lat is not None and raw.lon is not None:
            is_lat_valid = math.isfinite(raw.lat) and math.fabs(raw.lat) <= 90
            is_lon_valid = math.isfinite(raw.lon) and math.fabs(raw.lon) <= 180
            if is_lat_valid and is_lon_valid:
                lat = raw.lat
                lon = raw.lon
            else:
                print('WARNING: coordinates are invalid: {} {}'.format(raw.lat, raw.lon))

        skip = False
        text = self.convert_html_to_markdown(raw.text)
        if not text:
            print('WARNING: entry has no text: id={}'.format(raw.id))
        if not text and len(photos) == 0:
            print('WARNING: entry has no text and no photos, skipping: id={}'.format(raw.id))
            skip = True
        if text.find('dayone-moment:') != -1:
            print('WARNING: skipped previously-exported DayOne entry: id={}'.format(raw.id))
            skip = True

        if not skip:
            return ValidatedEntry(foreign_id=foreign_id, source_path=source_path, text=text, photos=photos, tags=tags,
                                  lat=lat, lon=lon, timestamp=timestamp, timezone=timezone)
        else:
            self.data.skipped_paths.append(source_path)
            return None

    def escape_tag(self, raw):
        tag = re.sub(r'\s+', r'\\\g<0>', raw)
        return tag

    def convert_html_to_markdown(self, original_text):
        soup = BeautifulSoup(original_text, 'html5lib')
        is_html = bool(soup.find())  # true if at least one HTML element can be found
        if is_html:
            return markdownify(original_text)
        else:
            return original_text

    def import_entries(self, entries: Iterable[ValidatedEntry]):
        flat_entries = list(entries)
        self.data.total_count = len(flat_entries)
        for entry in flat_entries:
            id, err = self.import_one_entry(entry)
            self.data.attempted_count += 1
            if not err:
                prefix = '[{}/{}]'.format(self.data.attempted_count, self.data.total_count)
                data = []
                if entry.text:
                    data.append('{} words'.format(len(entry.text.split())))
                if len(entry.tags):
                    data.append('{} tags'.format(len(entry.tags)))
                if len(entry.photos):
                    data.append('{} photos'.format(len(entry.photos)))
                if len(data):
                    print('{} Added new: {} -> {}: {}'.format(prefix, entry.foreign_id, id, ', '.join(data)))
                else:
                    print('{} Added new: {} -> {}'.format(prefix, entry.foreign_id, id))
                yield entry
            else:
                self.data.failed_paths.append(entry.source_path)
                print('ERROR: {}'.format(err))

    def import_one_entry(self, entry: ValidatedEntry) -> Tuple[Optional[str], Optional[str]]: # id, err
        args = self.build_dayone_args(entry)
        if self.debug:
            print(args)
        p = subprocess.run(args, input=entry.text, text=True, capture_output=True)
        if p.returncode == 0:
            id = self.parse_id_from_output(p.stdout)
            return id, None
        else:
            err = p.stderr
            return None, err

    def build_dayone_args(self, entry: ValidatedEntry):
        args = ['dayone2', '-j', self.target_journal_name]
        args.extend(['-d', entry.timestamp])
        args.extend(['-z', entry.timezone])
        if len(entry.tags) > 0:
            args.extend(['-t', *entry.tags])
        if len(entry.photos) > 0:
            args.extend(['-p', *entry.photos])
        if entry.lat and entry.lon:
            args.extend(['--coordinate', str(entry.lat), str(entry.lon)])
        args.extend(['--', 'new'])
        return args

    def parse_id_from_output(self, output):
        # E.g.: "Created new entry with uuid: CB17A357BED34F6D838410CA96C7D9D1"
        m = re.search(r'([A-F0-9]+)\s*$', output)
        if m:
            id = m.group(1)
            return id
        else:
            return ''

    def print_result(self, imported_entries: Iterable[ValidatedEntry]):
        succeeded_count = len(list(imported_entries))
        self.print_paths("SKIPPED", self.data.skipped_paths)
        self.print_paths("FAILED", self.data.failed_paths)
        skipped_count = len(self.data.skipped_paths)
        failed_count = len(self.data.failed_paths)
        print()
        print('{} succeeded, {} failed, {} skipped'.format(succeeded_count, failed_count, skipped_count))

    def print_paths(self, prefix, paths):
        if len(paths):
            print()
        for path in paths:
            print('{}: {}'.format(prefix, path))


if __name__ == '__main__':
    target_journal_name, src_directory = parse_args()
    i = Importer(src_directory, target_journal_name, debug=False)
    i.run()
