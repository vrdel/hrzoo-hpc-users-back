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
        if self._daemon:
            lfs = '%(levelname)s - %(message)s'
        else:
            lfs = '%(levelname)s ' + self._caller + ' - %(message)s'
        lf = logging.Formatter(lfs)
        lv = logging.INFO

        if not self.logger:
            logging.basicConfig(format=lfs, level=lv, stream=sys.stdout)
            self.logger = logging.getLogger(self._caller)

        if self._daemon:
            sth = logging.StreamHandler(stream=sys.stdout)
            sth.setFormatter(lf)
            sth.setLevel(lv)
            self.logger.addHandler(sth)

    def _init_syslog(self):
        lfs = '%(name)s[%(process)s]: %(levelname)s - %(message)s'
        lf = logging.Formatter(lfs)
        lv = logging.INFO

        if not self.logger:
            logging.basicConfig(format=lfs, level=lv)
            self.logger = logging.getLogger(self._caller)

        sh = logging.handlers.SysLogHandler('/dev/log', logging.handlers.SysLogHandler.LOG_USER)
        sh.setFormatter(lf)
        sh.setLevel(lv)
        self.logger.addHandler(sh)

    def _init_filelog(self):
        lfs = '%(asctime)s %(name)s[%(process)s]: %(levelname)s - %(message)s'
        lf = logging.Formatter(fmt=lfs, datefmt='%Y-%m-%d %H:%M:%S')
        lv = logging.INFO

        if not self.logger:
            logging.basicConfig(format=lfs, level=lv)
            self.logger = logging.getLogger(self._caller)

        sf = logging.handlers.WatchedFileHandler(self.logfile)
        self.logger.fileloghandle = sf.stream
        sf.setFormatter(lf)
        sf.setLevel(lv)
        self.logger.addHandler(sf)

    def __init__(self, caller, daemon, conf_loggers=None):
        self._caller = os.path.basename(caller)
        self._daemon = daemon

        try:
            if conf_loggers:
                if 'stdout' in conf_loggers:
                    self._init_stdout()
                if 'syslog' in conf_loggers:
                    self._init_syslog()
                if 'file' in conf_loggers:
                    self._init_filelog()
            else:
                self._init_stdout()
                self._init_syslog()
                self._init_filelog()
        except (OSError, IOError) as e:
            sys.stderr.write('ERROR ' + self._caller + ' - ' + str(e) + '\n')
            raise SystemExit(1)

    def get(self):
        if self._daemon:
            self.logger.propagate = False
        return self.logger
