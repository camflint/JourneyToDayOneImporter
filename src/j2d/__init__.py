import sys
import logging
from datetime import datetime
from logging import FileHandler


STDOUT_LEVEL = logging.INFO
STDOUT_FORMAT_STRING = "%(levelname)s :: %(message)s"
FILE_LEVEL = logging.DEBUG
FILE_FORMAT_STRING = "%(asctime)s %(levelname)s %(module)s %(funcName)s :: %(message)s"


# Logging to file

fh = FileHandler("j2d-{}.log".format(datetime.now().strftime(format="%Y%m%d-%H%M")))
fh.setLevel(FILE_LEVEL)
fh.setFormatter(logging.Formatter(FILE_FORMAT_STRING))

# Stdout/ipynb-output-cell
sh = logging.StreamHandler(sys.stdout)
sh.setLevel(STDOUT_LEVEL)
sh.setFormatter(logging.Formatter(STDOUT_FORMAT_STRING))

log = logging.getLogger()
log.setLevel(logging.NOTSET)
log.addHandler(fh)
log.addHandler(sh)
