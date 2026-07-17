import threading
import traceback

from typing import Dict, Any

import sublime
import sublime_plugin
import requests


from .vai_chat_tab import VaiChatTab
from .vai_endpoint_handler import OpenAIHandler


DEFAULT_TIMEOUT = 120


class VaiClearChatCommand(sublime_plugin.WindowCommand):
    """Command to clear the content of the chat tab."""

    def run(self):
        """Clear Chat Tab"""
        chat_tab = VaiChatTab()
        chat_tab.clear_chat_tab()


class VaiOpenAiChatCommand(sublime_plugin.WindowCommand):
    """Command to open and restore the AI chat tab."""

    def run(self):
        """Open the chat tab and restore its content if it exists."""
        chat_tab = VaiChatTab()
        chat_tab.ensure_chat_tab()  # create or focus the chat tab


class VaiSelectAssistantCommand(sublime_plugin.WindowCommand):
    """Command to select AI assistant from settings."""

    def run(self):
        # load settings
        settings = sublime.load_settings("vAI.sublime-settings")

        # show configured assistants
        self.assistants = settings.get("assistants", [])
        self.assistant_names = [a["name"] for a in self.assistants]
        if not self.assistants:
            sublime.message_dialog("No AI assistants configured in settings.")
            return

        self.window.show_quick_panel(self.assistant_names, self.on_select)

    def on_select(self, index):
        # save selected assistant into settings
        if index == -1:
            return

        settings = sublime.load_settings("vAI.sublime-settings")

        settings.set("selected_assistant", self.assistants[index]["name"])
        sublime.save_settings("vAI.sublime-settings")

        sublime.status_message(f"Selected assistant: {self.assistants[index]['name']}")


class VaiNewMessageCommand(sublime_plugin.WindowCommand):
    """Command to send user input and selection to the AI assistant."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.chat_tab = VaiChatTab()
        self.selected_text = ""
        self.settings = sublime.load_settings("vAI.sublime-settings")

    def run(self):
        # get text selection
        view = self.window.active_view()
        syntax = view.syntax().name.lower()

        selections = [view.substr(region) for region in view.sel() if not region.empty()]
        self.selected_text = self.get_markdown_formated_selection("\n".join(selections), syntax)

        # show user_input panel
        self.window.show_input_panel("Enter your query:", "", self.on_done, None, None)

    def on_done(self, user_input):
        # get selected assistant
        assistant = self.get_assistant()
        if assistant is None:
            return

        # create or focus chat tab before starting the thread
        # must be before construct_promt where it can be used
        self.chat_tab.ensure_chat_tab()

        # construct prompt
        prompt = self.construct_prompt(user_input)
        if prompt == "":
            return

        # start assistant thread
        thread = threading.Thread(target=self.query_assistant, args=(assistant, prompt, user_input))
        thread.start()

    def query_assistant(self, assistant: Dict[str, Any], prompt: str, user_input: str) -> None:
        """Sends request to the AI server and processes the response."""
        try:
            # mark and append user message to chat tab
            self.chat_tab.append_to_chat("\n## Question:\n")
            self.chat_tab.append_to_chat(prompt)

            # create handler
            role = assistant.get("assistant_role", "You are helpful assistant")
            handler = OpenAIHandler(role)

            # prepare request
            url = assistant["url"]
            model = assistant["chat_model"]
            payload = handler.prepare_payload(prompt, model)
            headers = {"Content-Type": "application/json"}
            if token := assistant.get("token"):
                headers.update(handler.get_token_header(token))

            # make request
            print(f"Sending request to: {url}")
            print(f"Payload: {payload}")
            print(f"Headers: {headers}")

            try:
                timeout = assistant.get("timeout", DEFAULT_TIMEOUT)
                response = requests.post(url, json=payload, stream=True, headers=headers, timeout=timeout)
                print(f"Response status: {response.status_code}")

                # parse response
                if response.status_code == 200:
                    # mark assistant's response in chat tab
                    self.chat_tab.append_to_chat("\n## Assistant:\n")

                    first_line = True
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode("utf-8")
                            if first_line:
                                print(f"First response line: {decoded_line[:300]}")
                                first_line = False
                            result = handler.process_response(decoded_line)

                            if result["response"]:
                                self.chat_tab.append_to_chat(result["response"])

                            if result["done"]:
                                self.chat_tab.append_to_chat("\n")
                                break
                else:
                    # print error
                    error_msg = f"ERROR when posting request to: {url}. {response.status_code} - {response.text}"
                    print(f"HTTP Error: {error_msg}")
                    self.chat_tab.show_error(error_msg)
            except Exception as request_error:
                error_msg = f"Request failed: {str(request_error)}"
                print(f"Request Exception: {error_msg}")
                self.chat_tab.show_error(error_msg)

        except Exception as e:
            error_msg = f"ERROR when contacting AI: {str(e)}"
            print(f"Detailed error: {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")
            self.chat_tab.show_error(error_msg)

    def construct_prompt(self, user_input: str):
        """Constructs prompt for chat."""

        # Handle :tabs [tabs_cnt | x..y | x,y,..] -> Construct prompt from content of specified tabs and prepend it to user_input
        if user_input.startswith(":tabs"):
            return self.construct_tabs_prompt(user_input)

        # Handle marks
        if user_input.startswith(":m") or user_input.startswith(":`"):
            return self.construct_marks_prompt(user_input)

        # Handle :: -> Take last query from settings and construct prompt like in simplest case
        if user_input.startswith("::"):
            user_input = self.settings.get("last_user_input", "")
            if user_input:
                return self.construct_simple_prompt(user_input, None)
            else:
                sublime.status_message("No previous user input found.")
                return ""

        # Handle simplest case: construct prompt from selection and user input
        return self.construct_simple_prompt(user_input, None)

    def construct_tabs_prompt(self, user_input: str):
        # Handle :tabs [tabs_cnt] -> Construct prompt from content of specified tabs and prepend it to user_input
        tab_contents = []
        num_tabs = 9  # maximum 9 tabs
        views = self.window.views()

        # Remove the :tabs prefix from the user input
        user_input = user_input[len(":tabs") :].strip()

        # Parse the tabs specification, at this moment supports only optional number of tabs to include
        tabs_spec = user_input.split()[0] if user_input else ""
        user_input = user_input[len(tabs_spec) :].strip() if tabs_spec else user_input

        # Get number of processed tabs
        if tabs_spec.isdigit():
            num_tabs = int(tabs_spec)

        # Get the contents of the specified tabs
        for view in views[:num_tabs]:
            content = view.substr(sublime.Region(0, view.size()))
            if content.strip():
                filename = view.file_name() or view.name() or "Untitled"
                formatted_content = f"FILE {filename}:\n{content}\n\n"
                tab_contents.append(formatted_content)

        # Concatenate the tabs contents and create prompt
        return self.construct_simple_prompt(user_input, "".join(tab_contents))

    def construct_marks_prompt(self, user_input: str):
        """Constructs prompt for chat."""

        # Handle :m -> Prints array of marked user_inputs from settings
        if user_input == ":m":
            self.chat_tab.append_to_chat("\n## Marks:\n")

            for mark in "abcdefghijklmnopqrstuvwxyz":
                if marked_input := self.settings.get(f"marked_input_{mark}", ""):
                    self.chat_tab.append_to_chat(f"{mark}: {marked_input}\n")
            return ""

        # Handle :m[a-z] user_input -> Mark user_input with a-z letter, save it to settings and construct prompt like in simplest case
        if user_input.startswith(":m") and len(user_input) > 2 and user_input[2].islower():
            mark = user_input[2]
            marked_input = user_input[3:].strip()

            self.settings.set(f"marked_input_{mark}", marked_input)
            sublime.save_settings("vAI.sublime-settings")

            return self.construct_simple_prompt(marked_input)

        # Handle :`[a-z] -> Take user_input under letter from settings and construct prompt like in simplest case
        if user_input.startswith(":`") and len(user_input) > 2 and user_input[2].islower():
            mark = user_input[2]
            marked_input = self.settings.get(f"marked_input_{mark}", "")
            if marked_input:
                return self.construct_simple_prompt(marked_input)
            else:
                sublime.status_message(f"No marked input found for '{mark}'.")

        return ""

    def construct_simple_prompt(self, user_input: str, selected_text=None):
        """Helper function to construct prompt from selection and user input."""

        if selected_text is None:
            selected_text = self.selected_text

        # Save the current user input for future use (in case of ::)
        self.settings.set("last_user_input", user_input)
        sublime.save_settings("vAI.sublime-settings")

        print("selected text3:", selected_text)
        return f"{selected_text}{user_input}"

    def get_markdown_formated_selection(self, selected_text: str, syntax: str) -> str:
        # TODO better doc Format selected text (if any)

        if md_lang := self.get_markdown_lang(syntax):
            return f"```{md_lang}\n{selected_text}\n```\n"

        return selected_text

    def get_markdown_lang(self, syntax):
        """Get code language for Markdown formatting."""
        md_lang_map = {
            "python": "python",
            "javascript": "javascript",
            "html": "html",
            "css": "css",
            "java": "java",
            "c++": "cpp",
            "c": "c",
            "ruby": "ruby",
            "go": "go",
            "rust": "rust",
            "json": "json",
            "xml": "xml",
            "bash": "bash",
            "shell script": "sh",
        }
        return md_lang_map.get(syntax, None)

    def get_assistant(self):
        """Get selected assistant details"""

        settings = sublime.load_settings("vAI.sublime-settings")
        selected_assistant_name = settings.get("selected_assistant", "")
        if not selected_assistant_name:
            sublime.message_dialog("No assistant selected. Use 'Select Assistant' first.")
            return None

        # get the full assistant details
        assistants = settings.get("assistants", [])
        assistant = next((a for a in assistants if a["name"] == selected_assistant_name), None)
        if not assistant:
            sublime.message_dialog(f"Assistant '{selected_assistant_name}' not found in default settings.")
            return None

        return assistant
