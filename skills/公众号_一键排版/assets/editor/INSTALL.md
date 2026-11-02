# Install the Orange WeChat editor

This skill includes the standalone editor in `index.html`. Install the editor before asking the skill to display an article in its interactive browser preview.

## Install

Copy the complete `assets/editor` folder from this skill to a permanent local folder, for example:

- macOS/Linux: `~/Applications/Orange-WeChat-Editor/`
- Windows: `%USERPROFILE%\\Applications\\Orange-WeChat-Editor\\`

The folder must contain `index.html`. No Node.js, npm packages, compilation, account, or public hosting is required. Keep the editor folder in place so drafts saved by the browser remain available.

## Open in the browser

Use a local web server so clipboard copy works consistently. In a terminal, change to the installed editor folder and run:

- macOS/Linux: `python3 -m http.server 4174`
- Windows: `py -m http.server 4174`

Then open `http://localhost:4174` in Chrome or Edge. Keep the terminal and browser tab open while working. If port 4174 is already in use, choose another free port and use that port in the browser address.

The left column contains the app name, copy-to-WeChat button, and formatting controls; the center column is the editable draft; the right column is a fixed phone preview at the reference ratio 1220:2816. After the skill loads an article, review the text and images in both the draft and preview, then use **复制到公众号** and paste into the WeChat Official Account editor.

## Bundled files

- `index.html` — standalone app, styles, selection tools, local draft saving, rich HTML copy, and phone preview.
- This bundle contains a generic sample only. It does not include the user's private article drafts or image assets.
