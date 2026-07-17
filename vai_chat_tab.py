import sublime


class VaiChatTab:
    """Class handling AI Chat Tab"""

    def __init__(self):
        self.window = sublime.active_window()

    def ensure_chat_tab(self):
        """Create new chat tab or focus existing one."""
        chat_view = self._find_chat_tab()

        if not chat_view:
            # get current layout
            layout = self.window.layout()

            # check if the layout has two columns
            if len(layout["cols"]) >= 3:
                # Check if the right column has an empty tab
                right_column_views = self.window.views_in_group(1)  # Group 1 is the right column
                if right_column_views:
                    # Find the first empty tab in the right column
                    for view in right_column_views:
                        if view.size() == 0 and not view.settings().get("vai_chat_tab"):
                            # Reuse this empty tab for the chat
                            chat_view = view
                            break

            # if no empty tab is found in the right column, create a new one
            if not chat_view:
                # If the layout is single-column, create a two-column layout
                if len(layout["cols"]) < 3:
                    # Set up a two-column layout with 70/30 split
                    self.window.run_command(
                        "set_layout",
                        {
                            "cols": [0.0, 0.7, 1.0],
                            "rows": [0.0, 1.0],
                            "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
                        },
                    )

                # create a new tab in the right column
                chat_view = self.window.new_file()
                chat_view.set_name("vAI Chat")
                chat_view.set_scratch(True)  # Don't prompt to save
                chat_view.settings().set("vai_chat_tab", True)
                chat_view.settings().set("word_wrap", True)

                # make the view read-only
                chat_view.set_read_only(True)

                # apply Markdown syntax highlighting
                chat_view.set_syntax_file("Packages/Markdown/Markdown.sublime-syntax")

                # move the new tab to the right column (group 1)
                self.window.set_view_index(chat_view, 1, 0)

            # restore saved chat content if it exists
            self.restore_chat_content(chat_view)

        # focus the chat tab
        self.window.focus_view(chat_view)

    def append_to_chat(self, text):
        sublime.set_timeout(lambda: self._append_to_chat(text), 0)

    def show_error(self, message):
        """Shows error message"""
        sublime.set_timeout(lambda: sublime.message_dialog(message), 0)
        # also append error to chat
        self.append_to_chat(f"\nERROR: {message}")

    def clear_chat_tab(self):
        if chat_view := self._find_chat_tab():
            chat_view.set_read_only(False)
            chat_view.run_command("select_all")
            chat_view.run_command("right_delete")

            sublime.status_message("Chat cleared")
        else:
            sublime.status_message("No chat tab found")

        settings = sublime.load_settings("vAI.sublime-settings")
        settings.set("chat_content", "")
        sublime.save_settings("vAI.sublime-settings")

    def save_chat_content(self, chat_view):
        """Save the chat content to settings."""
        if chat_view:
            settings = sublime.load_settings("vAI.sublime-settings")
            settings.set("chat_content", chat_view.substr(sublime.Region(0, chat_view.size())))
            sublime.save_settings("vAI.sublime-settings")

    def restore_chat_content(self, chat_view):
        """Restore the chat content from settings."""
        settings = sublime.load_settings("vAI.sublime-settings")
        chat_content = settings.get("chat_content", "")
        if chat_content:
            chat_view.set_read_only(False)
            chat_view.run_command("append", {"characters": chat_content})
            chat_view.set_read_only(True)

    def _find_chat_tab(self):
        """Find existing chat tab if it exists."""
        for view in self.window.views():
            if view.settings().get("vai_chat_tab"):
                return view
        return None

    def _append_to_chat(self, text):
        """Append text to chat tab. Must be called from main thread."""

        chat_view = self._find_chat_tab()
        if chat_view:
            # get the size of the view before appending
            last_position = chat_view.size()

            # append the text
            chat_view.set_read_only(False)
            chat_view.run_command("append", {"characters": text})
            chat_view.set_read_only(True)

            # scroll to the end
            chat_view.show(last_position)  # move the viewport to show the last position

            # ensure the very end is visible:
            chat_view.show(chat_view.size())

            # move the cursor to the end:
            chat_view.sel().clear()
            chat_view.sel().add(sublime.Region(chat_view.size()))
