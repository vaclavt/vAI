import sublime
import sublime_plugin
from .vai_chat_tab import VaiChatTab


class VaiChatTabEventListener(sublime_plugin.EventListener):
    def on_close(self, view):
        """Save chat content when the chat tab is closed."""
        if view.settings().get("vai_chat_tab"):
            chat_tab = VaiChatTab()
            chat_tab.save_chat_content(view)
