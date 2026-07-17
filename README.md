# vAI

vAI is a Sublime Text package that provides an interactive AI chat assistant
for OpenAI-compatible endpoints.

## Requirements

- Sublime Text 4, build 4000 or newer
- Python 3.8 plugin host
- The `requests` dependency

## Installation

Clone the repository into the Sublime Text Packages directory:

```bash
git clone https://github.com/vaclavt/vAI.git \
  "$HOME/Library/Application Support/Sublime Text/Packages/vAI"
```

Then run `Package Control: Satisfy Dependencies` from the Command Palette and
restart Sublime Text.

## Configuration

Copy `vAI.sublime-settings` to the Sublime Text User package directory:

```text
Packages/User/vAI.sublime-settings
```

Configure the assistant URL, model, and API token there. The repository
settings contain placeholder tokens and must not be replaced with real
credentials in a commit.

## Commands

- `vAI: Select Assistant`
- `vAI: Open AI Chat Tab`
- `vAI: Clear AI Chat Tab`
- `vAI: New Message`

## Package Control

The custom channel definition is available at:

```text
https://raw.githubusercontent.com/vaclavt/vAI/main/channel.json
```

Add that URL to the `channels` array in Package Control settings to install
the package through Package Control.

## License

MIT. See `LICENSE`.
