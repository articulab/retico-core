import logging
import structlog

# from structlog.stdlib._log_levels import add_log_level

# Step 1: Define TRACE level and register it
TRACE_LEVEL_NUM = 5

# add_log_level("trace", TRACE_LEVEL_NUM)
# structlog._log_levels
structlog.stdlib.NAME_TO_LEVEL["trace"] = TRACE_LEVEL_NUM
structlog.stdlib.LEVEL_TO_NAME[TRACE_LEVEL_NUM] = "trace"


# Add .trace to Logger
# def trace(self, message, *args, **kwargs):
#     if self.isEnabledFor(TRACE_LEVEL_NUM):
#         self._log(TRACE_LEVEL_NUM, message, args, **kwargs)


# logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")
# logging.Logger.trace = trace


# Step 2: Custom BoundLogger that supports .trace()
class CustomBoundLogger(structlog.stdlib.BoundLogger):
    def trace(self, event=None, **kw):
        return self._proxy_to_logger("trace", event, **kw)


# Step 3: Configure structlog to use stdlib + custom level
structlog.configure(
    wrapper_class=CustomBoundLogger,
    # logger_factory=structlog.stdlib.LoggerFactory(),
    processors=[
        # structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    cache_logger_on_first_use=True,
)

# # Step 4: Setup base logging
# logging.basicConfig(level=TRACE_LEVEL_NUM, format="%(message)s")

# Step 5: Use the logger
log = structlog.get_logger()
log.trace("This is a trace log")
log.debug("This is a debug log")
