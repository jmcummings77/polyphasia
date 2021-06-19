""" Pytest runner configuration. """


def pytest_configure(config):
    """ Configure the mypy plugin for pytest. """
    mypy = config.pluginmanager.getplugin("mypy")
    mypy.mypy_argv.extend(["--config-file", "testing_framework/mypy.ini"])
