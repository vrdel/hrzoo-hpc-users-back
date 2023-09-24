import logging
import logging.handlers
import sys
import os.path


class Logger(object):
    """
       Logger objects with initialized File and Syslog logger.
    """
    logger = None
    logfile = f"{os.environ['VIRTUAL_ENV']}/var/log/accounts-hpc.log"

    def _init_stdout(self):
        lfs = '%(levelname)s ' + self._caller + ' - %(message)s'
        lf = logging.Formatter(lfs)
        lv = logging.INFO

        logging.basicConfig(format=lfs, level=lv, stream=sys.stdout)
        self.logger = logging.getLogger(self._caller)

    def _init_syslog(self):
        lfs = '%(name)s[%(process)s]: %(levelname)s ' + self._caller + ' - %(message)s'
        lf = logging.Formatter(lfs)
        lv = logging.INFO

        sh = logging.handlers.SysLogHandler('/dev/log', logging.handlers.SysLogHandler.LOG_USER)
        sh.setFormatter(lf)
        sh.setLevel(lv)
        self.logger.addHandler(sh)

    def _init_filelog(self):
        lfs = '%(asctime)s %(name)s[%(process)s]: %(levelname)s ' + self._caller + ' - %(message)s'
        lf = logging.Formatter(fmt=lfs, datefmt='%Y-%m-%d %H:%M:%S')
        lv = logging.INFO

        sf = logging.handlers.RotatingFileHandler(self.logfile, maxBytes=511*1024, backupCount=5)
        self.logger.fileloghandle = sf.stream
        sf.setFormatter(lf)
        sf.setLevel(lv)
        self.logger.addHandler(sf)

    def __init__(self, caller):
        self._caller = os.path.basename(caller)
        try:
            self._init_stdout()
            self._init_filelog()
            self._init_syslog()
        except (OSError, IOError) as e:
            sys.stderr.write('ERROR ' + self._caller + ' - ' + str(e) + '\n')
            raise SystemExit(1)

    def get(self):
        return self.logger
