# -*- coding: utf-8 -*-

import sublime
import sublime_plugin
from perltidy.helpers import *


DEFAULT_SETTINGS = {
    'perltidy_enabled': True,
    'perltidy_log_level': 0,
    'perltidy_options': ['-sbl', '-bbt=1', '-pt=2', '-nbbc', '-l=100', '-ole=unix', '-w', '-se'],
    'perltidy_rc_paths': ['.perltidyrc', 'perltidyrc'],
}


class PerlTidyCommand(sublime_plugin.TextCommand):

    _perltidy_cmd = None
    _perltidy_log_level = None
    _perltidy_options = None
    _perltidy_rc_paths = None

    # Try to locate perltidy and set self._perltidy_cmd.
    def find_perltidy(self):

        # Determine perltidy command to run in the following order:
        # 1. From user setting "perltidy_cmd"
        # 2. Within PATH (search for "perltidy" or "perltidy.bat" on Windows)
        # 3. From platform specific defaults
        if self._perltidy_cmd is None:
            cmd = None

            try:
                # 1. From user setting "perltidy_cmd", this may be either a
                #    single string or a list, handle appropriately.
                cmd = self.view.settings().get('perltidy_cmd')
                if cmd is not None and type(cmd) is not list:
                    cmd = [cmd]

                if is_valid_perltidy_cmd(cmd, cmd_source='user', logger=self):
                    raise StopIteration()

                # 2. Within PATH (search for "perltidy" or "perltidy.bat" on Windows)
                cmd = find_perltidy_in_path(logger=self)
                if cmd is not None:
                    raise StopIteration()

                # 3. From platform specific defaults
                cmd = find_perltidy_in_platform_default_paths(logger=self)
                if cmd is not None:
                    raise StopIteration()

            except StopIteration:
                # Save command for later usage
                self.log(1, 'Using perltidy: ' + pp(cmd))
                self._perltidy_cmd = cmd
            else:
                pass

        return self._perltidy_cmd

    # Report to Sublime Text 2 whether PerlTidy is enabled, or not.
    def is_enabled(self):
        return self.view.settings().get('perltidy_enabled', DEFAULT_SETTINGS['perltidy_enabled'])

    # Load PerlTidy settings from Sublime preferences.
    def load_settings(self, reload=True):
        settings = self.view.settings()

        if reload or self._perltidy_log_level is None:
            self._perltidy_log_level = settings.get('perltidy_log_level', DEFAULT_SETTINGS['perltidy_log_level'])
        if reload or self._perltidy_options is None:
            self._perltidy_options = settings.get('perltidy_options', DEFAULT_SETTINGS['perltidy_options'])
        if reload or self._perltidy_rc_paths is None:
            self._perltidy_rc_paths = settings.get('perltidy_rc_paths', DEFAULT_SETTINGS['perltidy_rc_paths'])
        if reload and self._perltidy_cmd is not None:
            self._perltidy_cmd = None           # will be set by find_perltidy()

    # Simple logging.
    def log(self, level, message):
        if level <= self._perltidy_log_level:
            print 'PerlTidy: ' + message

    # Return current log level.
    def log_level(self):
        return self._perltidy_log_level

    # Main entry point for ST2.
    def run(self, edit):
        self.load_settings()

        # Bailout, if we don't have a valid perltidy command to run.
        if not self.find_perltidy():
            sublime.error_message(
                'PerlTidy: Cannot find perltidy in any directory given in environment variable ' +
                'PATH, nor in platform specific default locations. Please setup your environment ' +
                'variable PATH, so it contains perltidy, or specify perltidy location in user ' +
                'setting "perltidy_cmd". Please refer to documentation at ' +
                'https://github.com/rbo/st2-perltidy for details.')
            return

        # Check, if we have any non-empty regions and tidy them.
        regions_tidied = 0
        for region in self.view.sel():
            if not region.empty():
                regions_tidied += 1
                self.tidy_region(edit, region)

        # If no regions have been tidied so far, go ahead and tidy entire
        # view. Reposition cursor after tidying up.
        if regions_tidied == 0:
            cursor_pos = self.view.sel()[0]
            if self.tidy_region(edit, sublime.Region(0L, self.view.size())):
                if cursor_pos.empty():
                    self.view.sel().add(cursor_pos)
                    if len(self.view.sel()) > 1:
                        self.view.sel().subtract(self.view.sel()[1])
                    self.view.show_at_center(self.view.sel()[0].begin())

    # Tidy given region; returns True on success or False on perltidy runtime
    # error.
    def tidy_region(self, edit, region):

        # Build command.
        cmd = []
        cmd.extend(self._perltidy_cmd)
        cmd.extend(self._perltidy_options)

        # Check, if we have a perltidyrc in the current project and append to
        # command. TODO: Order should be user configurable.
        perltidyrc_path = find_perltidyrc_in_project(directories=self.view.window().folders(), perltidyrc_paths=self._perltidy_rc_paths, logger=self)
        if perltidyrc_path is not None:
            cmd.append('-pro=' + perltidyrc_path)

        # Run perltidy.
        success, output, error_output, error_hints = run_perltidy(cmd=cmd, input=self.view.substr(region), logger=self)

        if success:
            self.view.replace(edit, region, output)
            return True

        if len(error_hints):
            for hint in error_hints:
                self.log(0, hint)

        if error_output:
            results = self.view.window().new_file()
            results.set_scratch(True)
            results.set_name('PerlTidy: Error output')
            edit = results.begin_edit()
            results.insert(edit, 0, error_output)
            results.end_edit(edit)
        else:
            sublime.error_message(
                'PerlTidy: Unable to run perltidy. Please inspect console (hit Ctrl+` ' +
                'or select View->Show Console from menu) for detailed diagnostic ' +
                'messages, error output and hints.')

        return False
