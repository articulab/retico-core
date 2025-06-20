"""
Log Utils Module
================

This file defines the classes and functions of a new logging system for retico, which provides
retico modules with the capacity to create structured (dictionary) log messages that they can either
store in a log file, or print in the terminal.
The file is divided in 3 parts :
- Loggers & Functions : defines the terminal and file logger classes, and logging-related functions
for retico modules.
- Log filters : defines general filters that can be used in the log configuration to filter out the
desired log messages.
- Plot logs : defines general functions used for retico system's execution vizualization (after
execution, or in real time during an execution).
"""

import datetime
import logging
import os
import json
from pathlib import Path
import re
import threading
import time
import colorama
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import structlog


#############
# Log Filters
#############


def filter_has_key(_, __, event_dict, key):
    """Delete the log if it has the key in its event_dict.

    Args:
        event_dict (dict): the log message's dict, containing all parameters passed during logging.
        key (str): the key to match in event_dict.

    Returns:
        dict : returns the log_message's event_dict if it went through the filter.
    """
    if event_dict.get(key):
        raise structlog.DropEvent
    return event_dict


def filter_does_not_have_key(_, __, event_dict, key):
    """Delete the log if it doesn't have the key in its event_dict.

    Args:
        event_dict (dict): the log message's dict, containing all parameters passed during logging.
        key (str): the key to match in event_dict.

    Returns:
        dict : returns the log_message's event_dict if it went through the filter.
    """
    if not event_dict.get(key):
        raise structlog.DropEvent
    return event_dict


def filter_value_in_list(_, __, event_dict, key, values):
    """Delete the log if it has the key, and the corresponding value is in values.

    Args:
        event_dict (dict): the log message's dict, containing all parameters passed during logging.
        key (str): the key to match in event_dict.
        values (list[str]): values to match in event_dict.

    Returns:
        dict : returns the log_message's event_dict if it went through the filter.
    """
    if event_dict.get(key):
        if event_dict.get(key) in values:
            raise structlog.DropEvent
    return event_dict


def filter_value_not_in_list(_, __, event_dict, key, values):
    """Delete the log if it has the key, and the corresponding value is not in values.

    Args:
        event_dict (dict): the log message's dict, containing all parameters passed during logging.
        key (str): the key to match in event_dict.
        values (list[str]): values to match in event_dict.

    Returns:
        dict : returns the log_message's event_dict if it went through the filter.
    """
    if event_dict.get(key):
        if event_dict.get(key) not in values:
            raise structlog.DropEvent
    return event_dict


def filter_all_from_modules(_, __, event_dict):
    """function that filters all log message that has a `module` key.
    (every retico module binds this parameter, so it would delete every log from retico modules)

    Args:
        event_dict (dict): the log message's dict, containing all parameters passed during logging.

    Returns:
        dict : returns the log_message's event_dict if it went through the filter.
    """
    if event_dict.get("module"):
        raise structlog.DropEvent
    return event_dict


def filter_conditions(_, __, event_dict, conditions):
    """
    filter function for the structlog terminal logger.
    This function only keeps logs that matchs EVERY condition.
    A condition is a tuple (key, values). To verify the condition, the log message (a dict) has to
    have the `key`, and the value corresponding to the key in log message has to be in the
    condition's `values` list.

    Example :
    conditions = [("module":["Microphone Module"]), ("event":["create_iu", "append UM"])]
    Meaning of the conditions :
    KEEP IF module is "Microphone Module" AND event is in ["create_iu", "append UM"]

    Args:
        event_dict (dict): the log message's dict, containing all parameters passed during logging.
        conditions (list[tuple[str,list[str]]]): the conditions the event_dict needs to match.

    Returns:
        dict : returns the log_message's event_dict if it went through the filter.
    """
    for key, values in conditions:
        if event_dict.get(key):
            if event_dict.get(key) in values:
                continue
        raise structlog.DropEvent
    return event_dict


def filter_cases(_, __, event_dict, cases):
    """
    filter function for the structlog terminal logger.
    This function keeps logs that matchs ANY case. A case is a list of conditions, EVERY condition
    has to be verified to verify the case. ie. case == conditions, from the filter_conditions
    function.
    A condition is a tuple (key, values). To verify the condition, the log message (a dict) has to
    have the `key`, and the value corresponding to the key in log message has to be in the
    condition's `values` list.
    A case is a list of conditions, ie. a list of tuple (key, value).
    cases are a list of list of conditions.

    Example :
    cases = [[("module":["Micro"]), ("event":["create_iu", "append UM"])],
    [("module":["Speaker"]), ("event":["create_iu"])]]
    Meaning of the cases :
    KEEP IF ((module is "Microphone Module" AND event is in ["create_iu", "append UM"])
    OR (module is "Speaker Module" AND event is "append UM"))

    Args:
        event_dict (dict): the log message's dict, containing all parameters passed during logging.
        cases (list[list[tuple[str,list[str]]]]): the cases the event_dict needs to match.

    Returns:
        dict : returns the log_message's event_dict if it went through the filter.
    """
    for conditions in cases:
        boolean = True
        for key, values in conditions:
            if event_dict.get(key):
                if event_dict.get(key) in values:
                    continue
            boolean = False
        if boolean:
            return event_dict
    raise structlog.DropEvent


def filter_all_but_warnings_and_errors(_, __, event_dict):
    """function that filters all log message that is not a warning or an error.

    Args:
        event_dict (dict): the log message's dict, containing all parameters passed during logging.

    Returns:
        dict : returns the log_message's event_dict if it went through the filter.
    """
    cases = [
        [
            (
                "level",
                [
                    "warning",
                    "error",
                ],
            ),
        ],
    ]
    return filter_cases(_, _, event_dict, cases=cases)


def filter_all_but_info_warnings_and_errors(_, __, event_dict):
    """function that filters all log message that is not a warning or an error.

    Args:
        event_dict (dict): the log message's dict, containing all parameters passed during logging.

    Returns:
        dict : returns the log_message's event_dict if it went through the filter.
    """
    cases = [
        [
            (
                "level",
                [
                    "info",
                    "warning",
                    "error",
                ],
            ),
        ],
    ]
    return filter_cases(_, _, event_dict, cases=cases)


def filter_all(_, __, event_dict):
    """function that filters all log message that has a `module` key.
    (every retico module binds this parameter, so it would delete every log from retico modules)

    Args:
        event_dict (dict): the log message's dict, containing all parameters passed during logging.

    Returns:
        dict : returns the log_message's event_dict if it went through the filter.
    """
    raise structlog.DropEvent


#####################
# Loggers & Functions
#####################

def custom_add_log_level(
    logger, method_name, event_dict
):
    # event_dict["level"] = map_method_name(method_name)
    custom_log_level = event_dict.get("cl", None)
    level = custom_log_level if custom_log_level is not None else structlog._log_levels.map_method_name(method_name)
    event_dict["level"] = level

    return event_dict

def add_custom_log_level(name: str, num: int):
    """
    Add a custom logging level (e.g., TRACE) to both logging and structlog.
    """
    name_lower = name.lower()

    # Register with logging
    logging.addLevelName(num, name.upper())

    # Add method to logging.Logger
    def log_for_level(self, message, *args, **kwargs):
        if self.isEnabledFor(num):
            self._log(num, message, args, **kwargs)

    setattr(logging.Logger, name_lower, log_for_level)

    # Add method to structlog.stdlib.BoundLogger
    def structlog_for_level(self, event=None, **kw):
        return self._proxy_to_logger(name_lower, event, **kw)

    setattr(structlog.stdlib.BoundLogger, name_lower, structlog_for_level)
    setattr(structlog.PrintLogger, name_lower, structlog_for_level)


class TerminalLogger(structlog.BoundLogger):
    """Dectorator / Singleton class of structlog.BoundLogger, that is used to configure / initialize
    once the terminal logger for the whole system."""

    def __new__(cls, filters=[]):
        if not hasattr(cls, "instance"):

            def format_module(obj):
                splitted = str(obj).split(" ")
                if splitted[-1] == "Module":
                    splitted.pop(-1)
                return " ".join(splitted)

            def format_timestamp(obj):
                return str(obj[:-4])

            def format_on_type(obj):
                if isinstance(obj, bool):
                    return " ( " + str(obj) + " ) "
                if isinstance(obj, int):
                    return " | " + str(obj) + " | "
                return " " + str(obj)

            # level = logging.WARNING
            # level = 0
            # logging.basicConfig(level=level)
            # logging.getLogger("terminal").setLevel(0)

            cr = structlog.dev.ConsoleRenderer(
                colors=True,
                columns=[
                    structlog.dev.Column(
                        "timestamp",
                        structlog.dev.KeyValueColumnFormatter(
                            key_style=None,
                            value_style=colorama.Style.BRIGHT + colorama.Fore.BLACK,
                            reset_style=colorama.Style.RESET_ALL,
                            value_repr=format_timestamp,
                        ),
                    ),
                    structlog.dev.Column(
                        "level",
                        structlog.dev.LogLevelColumnFormatter(
                            level_styles={
                                key: colorama.Style.BRIGHT + level
                                for key, level in structlog.dev.ConsoleRenderer.get_default_level_styles().items()
                            },
                            reset_style=colorama.Style.BRIGHT + colorama.Style.RESET_ALL,
                            width=None,
                        ),
                    ),
                    structlog.dev.Column(
                        "module",
                        structlog.dev.KeyValueColumnFormatter(
                            key_style=None,
                            value_style=colorama.Fore.YELLOW,
                            reset_style=colorama.Style.RESET_ALL,
                            value_repr=format_module,
                            width=10,
                        ),
                    ),
                    structlog.dev.Column(
                        "event",
                        structlog.dev.KeyValueColumnFormatter(
                            key_style=None,
                            value_style=colorama.Style.BRIGHT + colorama.Fore.WHITE,
                            reset_style=colorama.Style.RESET_ALL,
                            value_repr=str,
                            width=40,
                        ),
                    ),
                    structlog.dev.Column(
                        "",
                        structlog.dev.KeyValueColumnFormatter(
                            key_style=colorama.Fore.MAGENTA,
                            value_style=colorama.Style.BRIGHT + colorama.Fore.CYAN,
                            reset_style=colorama.Style.RESET_ALL,
                            value_repr=format_on_type,
                        ),
                    ),
                ],
            )

            # configure structlog to have a terminal logger
            processors = (
                [
                    structlog.processors.TimeStamper(fmt="%H:%M:%S.%f"),
                    # structlog.processors.add_log_level,
                    custom_add_log_level,
                ]
                + filters
                + [cr]
            )
            structlog.configure(
                processors=processors,
                wrapper_class=structlog.stdlib.BoundLogger,
                # logger_factory=structlog.stdlib.LoggerFactory(),
                # logger_factory=structlog.PrintLoggerFactory(),
                cache_logger_on_first_use=True,
            )
            terminal_logger = structlog.get_logger("terminal")

            # log info to cache the logger, using the config's cache_logger_on_first_use parameter
            terminal_logger.debug("init terminal logger", cl="abstract")

            # set the singleton instance
            cls.instance = terminal_logger
        return cls.instance


class TerminalLogger2:

    def __init__(self, verbosity_level=0, filters=None, **kwargs):
        self.verbosity_level = verbosity_level
        self.logger = TerminalLogger(filters=filters, **kwargs)
        print("verbosity level", self.verbosity_level)

    def bind(self, **kwargs):
        self.logger = self.logger.bind(**kwargs)
        return self

    def _wrap(self, level_name, event, *args, **kwargs):
        print("wrapping", self.verbosity_level, level_name)
        if self.verbosity_level == 0:
            return None
        elif self.verbosity_level == 1 and level_name == "debug":
            super_method = getattr(self.logger, level_name)
            return super_method(event, *args, **kwargs)
        else:
            super_method = getattr(self.logger, level_name)
            return super_method(event, *args, **kwargs)

    def info(self, event=None, *args, **kwargs):
        print("info", event, *args, **kwargs)
        return self._wrap("info", event, *args, **kwargs)

    def debug(self, event=None, *args, **kwargs):
        return self._wrap("debug", event, *args, **kwargs)

    def warning(self, event=None, *args, **kwargs):
        return self._wrap("warning", event, *args, **kwargs)

    def error(self, event=None, *args, **kwargs):
        return self._wrap("error", event, *args, **kwargs)

    def critical(self, event=None, *args, **kwargs):
        return self._wrap("critical", event, *args, **kwargs)

    def exception(self, event=None, *args, **kwargs):
        return self._wrap("exception", event, *args, **kwargs)


class FileLogger(structlog.BoundLogger):
    """Dectorator / Singleton class of structlog.BoundLogger, that is used to configure / initialize
    once the file logger for the whole system."""

    def __new__(cls, filters=[], log_path="logs/run"):
        if not hasattr(cls, "instance"):
            structlog.configure(
                processors=[
                    structlog.processors.add_log_level,
                    structlog.processors.TimeStamper(fmt="iso"),
                ]
                + filters
                + [
                    structlog.processors.ExceptionRenderer(),
                    structlog.processors.JSONRenderer(),
                ],
                logger_factory=structlog.WriteLoggerFactory(file=Path(log_path).open("wt", encoding="utf-8")),
                cache_logger_on_first_use=True,
            )
            file_logger = structlog.get_logger("file_logger")

            # log info to cache the logger, using the config's cache_logger_on_first_use parameter
            file_logger.info("init file logger")

            # set the singleton instance
            cls.instance = file_logger
        return cls.instance


class FileLogger2:

    def __init__(self, verbosity_level=0, filters=None, **kwargs):
        self.verbosity_level = verbosity_level
        self.logger = FileLogger(filters=filters, **kwargs)
        self.logger.set_verbosity

    def bind(self, **kwargs):
        self.logger = self.logger.bind(**kwargs)
        return self

    def _wrap(self, level_name, event, *args, **kwargs):
        if self.verbosity_level == 0:
            return None
        elif self.verbosity_level == 1 and level_name == "debug":
            super_method = getattr(self.logger, level_name)
            return super_method(event, *args, **kwargs)
        else:
            super_method = getattr(self.logger, level_name)
            return super_method(event, *args, **kwargs)

    def info(self, event=None, *args, **kwargs):
        return self._wrap("info", event, *args, **kwargs)

    def debug(self, event=None, *args, **kwargs):
        return self._wrap("debug", event, *args, **kwargs)

    def warning(self, event=None, *args, **kwargs):
        return self._wrap("warning", event, *args, **kwargs)

    def error(self, event=None, *args, **kwargs):
        return self._wrap("error", event, *args, **kwargs)

    def critical(self, event=None, *args, **kwargs):
        return self._wrap("critical", event, *args, **kwargs)

    def exception(self, event=None, *args, **kwargs):
        return self._wrap("exception", event, *args, **kwargs)


def create_new_log_folder(log_folder):
    """Function that creates a new folder to store the current run's log file. Find the last run's
    number and creates a new log folder with an increment of 1.

    Args:
        log_folder (str): the log_folder path where every run's log folder is stored.

    Returns:
        str: returns the final path of the run's log_file, with a format : logs/run_33/logs.log
    """
    cpt = 0
    log_folder_full_path = log_folder + "_" + str(cpt)
    while os.path.isdir(log_folder_full_path):
        cpt += 1
        log_folder_full_path = log_folder + "_" + str(cpt)
    os.makedirs(log_folder_full_path)
    filepath = log_folder_full_path + "/logs.log"
    return filepath


def configurate_logger(
    log_path="logs/run",
    filters=None,
    filters_terminal=[filter_all_but_info_warnings_and_errors],
    filters_file=[filter_all],
):
    """
    Configure structlog's logger and set general logging args (timestamps,
    log level, etc.)

    Args:
        log_path: (str): logs folder's path.
        filters: (list): list of function that filters logs that will be outputted in the terminal.
    """
    if filters_file != [filter_all] or filters is not None:
        log_path = create_new_log_folder(log_path)

    # add_custom_log_level("abstract", 9)
    # add_custom_log_level("trace", 1)
    terminal_logger = TerminalLogger(filters=filters if filters is not None else filters_terminal)
    file_logger = FileLogger(log_path=log_path, filters=filters if filters is not None else filters_file)
    return terminal_logger, file_logger


def log_exception(module, exception):
    """function that enable modules to log the encountered exceptions to both logger (terminal and
    file) in
    a unified way (and factorize code).

    Args:
        module (object): the module that encountered the exception.
        exception (Exception): the encountered exception.
    """
    module.terminal_logger.exception("The module encountered the following exception while running :")
    module.file_logger.exception(
        "The module encountered the following exception while running :",
    )
    # could introduce errors while parsing the json logs,
    # because of the " chars in the exception tracebacks
    # module.file_logger.exception(
    #     "The module encountered the following exception while running :",
    #     tarcebacks=[
    #         tb.replace('"', "'") for tb in traceback.format_tb(exception.__traceback__)
    #     ],
    # )


###########
# Plot logs
###########

THREAD_ACTIVE = False
REFRESHING_TIME = 1
LOG_FILE_PATH = None
PLOT_SAVING_PATH = None
PLOT_CONFIG_PATH = None


def store_log(
    log_data,
    events,
    event_name_in_config,
    event_name_for_plot,
    module_name_for_plot,
    date,
):
    """function used to add to log_data the log events and their timestamps if they match the
    config_file conditions.

    Args:
        log_data (dict): the data structure where the logs that will be plotted are stored.
        events (dict): dictionary containing all events to plot for that event.
        event_name_in_config (str): the event name in log message.
        event_name_for_plot (str): the log's event name.
        module_name_for_plot (str): A shorter version of the module's name (for the plot).
        date (date): the log's timestamp.

    Returns:
        tuple[dict[],bool]: Returns the logs storing data structure, and a boolean that is True if
        the event has been stored, False if it hasn't.
    """
    is_event_in_config = events is not None and event_name_in_config in events
    if is_event_in_config and not ("exclude" in events[event_name_in_config]):
        if event_name_for_plot not in log_data["events"]:
            log_data["events"][event_name_for_plot] = {"x_axis": [], "y_axis": []}
            if "plot_settings" in events[event_name_in_config]:
                # print(
                #     f"plot_config[module_name_in_config]['events'] {plot_config[module_name_in_config]['events']}"
                # )
                log_data["events"][event_name_for_plot]["plot_settings"] = events[event_name_in_config]["plot_settings"]
        log_data["events"][event_name_for_plot]["y_axis"].append(module_name_for_plot)
        log_data["events"][event_name_for_plot]["x_axis"].append(date)
    return log_data, is_event_in_config


def plot(
    log_file_path,
    plot_saving_path,
    plot_config,
    events_all_modules,
    log_data={"events": {}},
    line_cpt=0,
    window_duration=None,
):
    """function used to create a plot for a system run from the corresponding log file. Can be used
    to plot live or after the execution.

    Args:
        log_file_path (str, optional): path to the folder corresponding to the desired run to plot.
            Defaults to None.
        plot_saving_path (str, optional): path to the folder where the plot will be saved. Defaults
            to None.
        plot_config (dict): the plot_config contains the events that will be plotted, and their
            corresponding plot information.
        events_all_modules (dict): the log events that will be retrieved for every module.
        log_data (dict, optional): If called from the plot_live function, used to store current
            log_file logs and only retrieve new logs at each loop of live plotting. Defaults to
            {"events": {}}.
        line_cpt (int, optional): If called from the plot_live function, used to only retrieve new
            logs at each loop of plot_live (log line > line_cpt). Defaults to 0.
        window_duration (int, optional): a fixed time window (in seconds) preceding the current time
            which defines all the logs that will be used for the real-time plot. Defaults to None.


    Returns:
        tuple[dict[],int]: Returns the already retrieved and processed logs with the line_cpt to the
        last line processed. Used to only process new logs at each plot_live loop.
    """
    nb_pb_line = 0
    terminal_logger = TerminalLogger()

    with open(log_file_path, encoding="utf-8") as f:
        lines = f.readlines()
        first_line = lines[0]
        first_line_date = datetime.datetime.fromisoformat(json.loads(first_line)["timestamp"])
        # last_line = lines[-1]
        # last_line_date = datetime.datetime.fromisoformat(
        #     json.loads(last_line)["timestamp"]
        # )
        new_pointer = len(lines)
        lines = lines[line_cpt:]
        line_cpt = new_pointer

    # Retrieve logs : store data from log_file to log_data if a matching pair of "module" and
    # "event" can be found in plot_config
    for l in lines:
        try:
            log = json.loads(l)

            module_name = log["module"] if "module" in log else None
            event_name = log["event"] if "event" in log else None

            if module_name is None:
                continue

            date = datetime.datetime.fromisoformat(log["timestamp"])
            date_plt = mdates.date2num(date)
            module_name_for_plot = module_name.split(maxsplit=1)[0]

            # log from event, from most specific to least specific
            events_specific_module = None
            if module_name in plot_config and "events" in plot_config[module_name]:
                events_specific_module = plot_config[module_name]["events"]

            # if we specified in the config to log specific event from specific module
            log_data, has_been_stored = store_log(
                log_data,
                events_specific_module,
                event_name,
                module_name_for_plot + "_" + event_name,
                module_name_for_plot,
                date_plt,
            )
            if has_been_stored:
                continue

            # if we specified in the config to log specific event from any module
            log_data, has_been_stored = store_log(
                log_data,
                events_all_modules,
                event_name,
                event_name,
                module_name_for_plot,
                date_plt,
            )
            if has_been_stored:
                continue

            # if we specified in the config to log any event from specific module
            log_data, has_been_stored = store_log(
                log_data,
                events_specific_module,
                "other_events",
                "other_events_" + module_name_for_plot,
                module_name_for_plot,
                date_plt,
            )
            if has_been_stored:
                continue

            # if we specified in the config to log any event from any module
            log_data, has_been_stored = store_log(
                log_data,
                events_all_modules,
                "other_events",
                "other_events",
                module_name_for_plot,
                date_plt,
            )

        except Exception:
            terminal_logger.exception("exception store log")
            nb_pb_line += 1

    _, ax = plt.subplots(figsize=(10, 5))

    # REORDER Y-AXIS
    # create a simulation axis to reorder the plot's y-axis (module names)
    # to respect the module order from the plot configuration file
    module_order_y_axis = [m.split(" ")[0] for m in plot_config.keys() if m != "any_module"][::-1]
    dates_order_y_axis = [mdates.date2num(first_line_date) for i in range(len(module_order_y_axis))]
    ax.plot(
        dates_order_y_axis,
        module_order_y_axis,
        ".",
        color="white",
        label="",
        markersize=1,
    )

    # put all events data in the plot
    try:
        # REORDER MARKER LAYERS
        # reorder log_data so that marker layers respect events order from config
        events = log_data["events"].keys()
        ordered_events = []
        for m_name_conf, m_data in plot_config.items():
            m_name_plot = m_name_conf.split(" ")[0] if m_name_conf != "any_module" else ""
            for e_name_conf, e_data in m_data["events"].items():
                if "exclude" not in e_data:
                    for e_name_plot in events:
                        if m_name_plot in e_name_plot and e_name_conf in e_name_plot:
                            ordered_events.append(e_name_plot)

        # reverse the order to have the first in config plotted in last
        for e_name_plot in ordered_events[::-1]:
            event_data = log_data["events"][e_name_plot]
            x = event_data["x_axis"]
            y = event_data["y_axis"]

            if "plot_settings" in event_data:
                ax.plot(
                    x,
                    y,
                    event_data["plot_settings"]["marker"],
                    color=event_data["plot_settings"]["marker_color"],
                    label=e_name_plot,
                    markersize=event_data["plot_settings"]["marker_size"],
                )
            else:
                ax.plot(
                    event_data["x_axis"],
                    event_data["y_axis"],
                    "|",
                    color="lightslategrey",
                    label=e_name_plot,
                    markersize=20,
                )
    except Exception:
        terminal_logger.exception()

    ## create and save the plot

    # legend
    ax.legend(fontsize="7", loc="center left")
    # REORDER LEGEND
    # re-reversed to match config order
    handles = plt.gca().get_legend().legend_handles[::-1]
    for h in handles:
        h.set_markersize(3 * np.log(h.get_markersize()))
    plt.legend(handles, ordered_events)

    # dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%M:%S"))
    if window_duration is not None:
        last_date = datetime.datetime.fromisoformat(json.loads(lines[-1])["timestamp"])
        padding = 5
        end_window = last_date + datetime.timedelta(seconds=last_date.second % padding)
        start_window = end_window - datetime.timedelta(seconds=window_duration)
        ax.set_xlim(left=start_window, right=end_window)

    # ticks
    ax.grid(True)
    ax.xaxis.set_major_locator(mdates.SecondLocator(bysecond=range(0, 61, 5)))
    ax.xaxis.set_minor_locator(mdates.SecondLocator(bysecond=range(0, 61, 1)))
    plt.xticks(fontsize=7)

    # save plot
    plot_filename = plot_saving_path + "/plot_IU_exchange.png"
    plt.savefig(plot_filename, dpi=200, bbox_inches="tight")
    plt.close()

    return log_data, line_cpt


def extract_number(string):
    """extract the number from the string.

    Args:
        string (str): string to analyze.

    Returns:
        int: the extracted number.
    """
    s = re.findall("\d+$", string)
    return (int(s[0]) if s else -1, string)


def plot_live():
    """a looping function that creates a plot from the current run's log_file each `REFRESHING_TIME`
    seconds (if it's the biggest run number in your `logs` folder)
    """
    global LOG_FILE_PATH, PLOT_SAVING_PATH

    if LOG_FILE_PATH is None or PLOT_SAVING_PATH is None:
        subfolders = [f.path for f in os.scandir("logs/") if f.is_dir()]
        max_run = max(subfolders, key=extract_number)
        LOG_FILE_PATH = max_run + "/logs.log"
        PLOT_SAVING_PATH = "run_plots/" + max_run.split("/")[-1]
        if not os.path.isdir(PLOT_SAVING_PATH):
            os.makedirs(PLOT_SAVING_PATH)

    if PLOT_CONFIG_PATH is None:
        raise NotImplementedError
    else:
        with open(PLOT_CONFIG_PATH, encoding="utf-8") as f:
            plot_config = json.load(f)

    events_all_modules = None
    if "any_module" in plot_config and "events" in plot_config["any_module"]:
        events_all_modules = plot_config["any_module"]["events"]

    log_data = {"events": {}}
    line_cpt = 0

    while THREAD_ACTIVE:
        time.sleep(REFRESHING_TIME)
        log_data, line_cpt = plot(
            log_file_path=LOG_FILE_PATH,
            plot_saving_path=PLOT_SAVING_PATH,
            plot_config=plot_config,
            events_all_modules=events_all_modules,
            log_data=log_data,
            line_cpt=line_cpt,
            window_duration=WINDOW_DURATION,
        )


def plot_once(plot_config_path, log_file_path=None, plot_saving_path=None):
    """Create a plot for a previous system run from the corresponding log file.

    Args:
        plot_config_path (str): the path to the plot configuration file.
        log_file_path (str, optional): path to the folder corresponding to the desired run to plot.
            Defaults to None.
        plot_saving_path (str, optional): path to the folder where the plot will be saved. Defaults
            to None.
    """
    if log_file_path is None or plot_saving_path is None:
        subfolders = [f.path for f in os.scandir("logs/") if f.is_dir()]
        max_run = max(subfolders, key=extract_number)
        log_file_path = max_run + "/logs.log"
        plot_saving_path = "run_plots/" + max_run.split("/")[-1]
        if not os.path.isdir(plot_saving_path):
            os.makedirs(plot_saving_path)
    with open(plot_config_path, encoding="utf-8") as f:
        plot_config = json.load(f)
    events_all_modules = None
    if "any_module" in plot_config and "events" in plot_config["any_module"]:
        events_all_modules = plot_config["any_module"]["events"]
    plot(
        log_file_path=log_file_path,
        plot_saving_path=plot_saving_path,
        plot_config=plot_config,
        events_all_modules=events_all_modules,
    )


def setup_plot_live():
    """a function that initializes and starts a thread from the looping function `plot_live`, to
    create a plot from the log_file in real time passively."""
    if THREAD_ACTIVE:
        threading.Thread(target=plot_live).start()


def stop_plot_live():
    """a function that stops plot_live's thread. Supposed to be called at the end of the run by the
    `network`"""
    global THREAD_ACTIVE
    THREAD_ACTIVE = False


def configurate_plot(
    is_plot_live=False,
    refreshing_time=1,
    plot_config_path=None,
    log_file_path=None,
    plot_saving_path=None,
    window_duration=5,
):
    """A function that configures the global parameters related to plot configuration.
    These global parameters will be used by the `plot_live` function to create a plot from
    the current run's log_file in real time.

    Args:
        plot_live (bool, optional): If set to True, a plot from the current run's log_file will be
            created in real time. If set to False, it will only be created at the end of the run.
            Defaults to False.
        refreshing_time (int, optional): The refreshing time (in seconds) between two creation of
            plots when `plot_live` is set to `True`. Defaults to 1.
        plot_config_path (str): the path to the plot configuration file.
        log_file_path (str, optional): path to the folder corresponding to the desired run to plot.
            Defaults to None.
        plot_saving_path (str, optional): path to the folder where the plot will be saved. Defaults
            to None.
        window_duration (int, optional): a fixed time window (in seconds) preceding the current time
            which defines all the logs that will be used for the real-time plot. Defaults to 5.
    """
    global THREAD_ACTIVE, REFRESHING_TIME, LOG_FILE_PATH, PLOT_SAVING_PATH, PLOT_CONFIG_PATH
    global WINDOW_DURATION
    THREAD_ACTIVE = is_plot_live
    REFRESHING_TIME = refreshing_time
    PLOT_CONFIG_PATH = plot_config_path
    LOG_FILE_PATH = log_file_path
    PLOT_SAVING_PATH = plot_saving_path
    WINDOW_DURATION = window_duration


if __name__ == "__main__":
    plot_once("configs/plot_config_simple.json")
