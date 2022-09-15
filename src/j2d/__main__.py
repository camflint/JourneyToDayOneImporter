import os
import sys
from .j2d import Importer


def parse_args():
    args = sys.argv
    if len(args) < 3:
        raise RuntimeError('missing [dest_journal_name] and/or [src_directory] arguments')
    dest_journal_name = sys.argv[1]
    src_directory = os.path.expanduser(sys.argv[2])
    if not os.path.exists(src_directory):
        raise RuntimeError('directory is missing or invalid')
    return dest_journal_name, src_directory


target_journal_name, src_directory = parse_args()
i = Importer(src_directory, target_journal_name)
i.run()
