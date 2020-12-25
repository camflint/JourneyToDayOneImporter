import math
import os
import re
import sys
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Iterable

from pytz import timezone as tz, UnknownTimeZoneError
from tzlocal import get_localzone


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
class ImporterStatistics:
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


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
    def __init__(self, src_directory, target_journal_name):
        self.src_directory = src_directory
        self.target_journal_name = target_journal_name
        self.retryList = []
        self.stats = ImporterStatistics()

    def run(self):
        entries = self.load_journey_entries(self.src_directory)
        self.import_entries(entries)
        self.print_stats()

    def load_journey_entries(self, root):
        for file in self.iter_journey_files(root):
            yield self.load_entry(file)

    def iter_journey_files(self, root):
        p = Path(root)
        for file in p.rglob('*.json'):
            yield file

    def load_entry(self, file):
        with open(file) as f:
            text = f.read()
            body = json.loads(text)
            entry = self.extract_entry_from_body(body, file)
            return entry

    def extract_entry_from_body(self, body, path):
        return JourneyEntry(id=body['id'], date_journal=body['date_journal'], text=body['text'], lon=body['lon'],
                            lat=body['lat'], tags=body['tags'], photos=body['photos'], address=body['address'],
                            type=body['type'], timezone=body['timezone'], path=path)

    def import_entries(self, entries: Iterable[JourneyEntry]):
        for entry in entries:
            if not len(entry.text) > 0:
                self.stats.skipped += 1
                continue
            id, err = self.import_one_entry(entry)
            if not err:
                self.stats.succeeded += 1
                print('Added: {} -> {}'.format(entry.id, id))
            else:
                self.stats.failed += 1
                self.retryList.append(entry.path)
                print('ERROR: {}'.format(err))

    def import_one_entry(self, entry: JourneyEntry):
        id = ''
        err = ''
        args = self.build_dayone_args(entry)
        print(args)
        p = subprocess.run(args, input=entry.text, text=True, capture_output=True)
        if p.returncode == 0:
            # Parse entry ID. E.g.: Created new entry with uuid: CB17A357BED34F6D838410CA96C7D9D1
            m = re.search(r'([A-F0-9]+)\s*$', p.stdout)
            if m:
                id = m.group(1)
        else:
            err = p.stderr
        return id, err

    def build_dayone_args(self, entry: JourneyEntry):
        args = ['dayone2', '-j', self.target_journal_name]

        timezone = ''
        if entry.timezone:
            try:
                timezone = tz(entry.timezone).zone
            except UnknownTimeZoneError:
                print('WARNING: timezone is invalid: {}'.format(entry.timezone))
        if not timezone:
            timezone = get_localzone().zone
        args.extend(['-z', timezone])

        timestamp = ''
        timestamp_format = '%Y-%m-%d %I:%M:%S %p'
        if entry.date_journal is not None:
            try:
                dt = datetime.fromtimestamp(entry.date_journal / 1000)
                timestamp = dt.strftime(timestamp_format)
            except (OverflowError, ValueError, OSError):
                print('WARNING: timestamp is invalid: {}'.format(entry.date_journal))
        if not timestamp:
            dt = datetime.now(tz(timezone))
            timestamp = dt.strftime(timestamp_format)
        args.extend(['-d', timestamp])

        if entry.lat is not None and entry.lon is not None:
            is_lat_valid = math.isfinite(entry.lat) and math.fabs(entry.lat) <= 90
            is_lon_valid = math.isfinite(entry.lon) and math.fabs(entry.lon) <= 180
            if is_lat_valid and is_lon_valid:
                args.extend(['--coordinate', str(entry.lat), str(entry.lon)])
            else:
                print('WARNING: coordinates are invalid: {} {}'.format(entry.lat, entry.lon))

        if len(entry.tags) > 0:
            tag_names = map(lambda t: re.sub(r'\s+', r'\\\g<0>', t), entry.tags)
            args.extend(['-t', *tag_names])

        if len(entry.photos) > 0:
            valid_paths = []
            for path in entry.photos:
                abs_path = os.path.abspath(os.path.join(self.src_directory, path))
                if os.path.exists(abs_path) and os.path.isfile(abs_path):
                    valid_paths.append(abs_path)
                else:
                    print('WARNING: photo path is invalid: {}'.format(abs_path))
            args.extend(['-p', *valid_paths])

        args.extend(['--', 'new'])

        return args

    def print_stats(self):
        print()
        print('{} succeeded, {} failed, {} skipped'.format(self.stats.succeeded, self.stats.failed, self.stats.skipped))


if __name__ == '__main__':
    target_journal_name, src_directory = parse_args()
    i = Importer(src_directory, target_journal_name)
    i.run()
