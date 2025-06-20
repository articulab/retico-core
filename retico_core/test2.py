import logging
import structlog
from structlog.stdlib import BoundLogger, LoggerFactory, _FixedFindCallerLogger


VERBOSE = 7
TRACE   = 3


def register_custom_levels():
    logging.addLevelName(VERBOSE, "verbose")
    logging.addLevelName(TRACE, "trace")

    structlog.stdlib.LEVEL_TO_NAME[VERBOSE] = "verbose"
    structlog.stdlib.NAME_TO_LEVEL["verbose"] = VERBOSE

    structlog.stdlib.LEVEL_TO_NAME[TRACE] = "trace"
    structlog.stdlib.NAME_TO_LEVEL["trace"] = TRACE


class VerboseStdLogger(_FixedFindCallerLogger):
    def verbose(self, event, *args, **kwargs):
        return self._log(VERBOSE, msg=event, args=args, **kwargs)

    def trace(self, event, *args, **kwargs):
        return self._log(TRACE, msg=event, args=args, **kwargs)


class VerboseLoggerFactory(LoggerFactory):
    def __init__(self, *args, ignore_frame_names=None, **kwargs):
        # Skip calling structlog.stdlib.LoggerFactory.__init__() directly
        #   to prevent setLoggerClass() from being overwritten!
        #   See: `register_std_logger()`
        # Alternatively, find a reliable way to wait for `LoggerFactory`'s init
        #   to run first, in which case this custom factory is unnecessary
        self._ignore = ignore_frame_names or []


class VerboseLogger(BoundLogger):
    '''
    `structlog.BoundLogger` wrapper that exposes two additional log levels:

    * `Verbose (7)`
    * `Trace   (3)`
    '''
    def verbose(self, event, **kwargs):
        return self.log(VERBOSE, event, **kwargs)

    def trace(self, event, **kwargs):
        return self.log(TRACE, event, **kwargs)


def configure_structlog():
    structlog.configure(
        wrapper_class=VerboseLogger,
        logger_factory=VerboseLoggerFactory(),
        processors=[
            ...
        ],
    )


def register_std_logger():
    if logging.getLoggerClass() is not VerboseStdLogger:
        logging.setLoggerClass(VerboseStdLogger)


def configure():
    '''
    Adds custom log levels and perform initial `structlog` setup.

    Run this method at app/script startup, 
    **before** any `structlogger.get_logger()` invocations!
    '''
    # Fix verbose logger
    register_std_logger()

    # Register custom logging levels
    register_custom_levels()

    # Set up structlog
    configure_structlog()
    
    
configure()

log = structlog.get_logger("test")
log.info("info")
log.trace("trace")