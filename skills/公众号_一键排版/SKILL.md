---
name: gzh-one-click-layout
description: Format a user-provided Chinese article and images for their WeChat Official Account editor using the user's established typography, emphasis, heading, and caption rules. Use when they provide an Obsidian draft, document, pasted article, or image-and-text content and ask for WeChat formatting.
---

# 公众号_一键排版

Turn the user's supplied article into a formatted draft in their local Orange WeChat editor, with a live phone preview. The user may provide the source from Obsidian, another local file, an attachment, or pasted content. Preserve the article; this is a layout task, not a rewrite.

## Workflow

1. **Find and read the source.** Use the path, Obsidian vault context, or attachments supplied in the request. Read the complete article and identify its title, section breaks, paragraph boundaries, images, and any image captions. For Markdown/HTML/MHTML, preserve image order and resolve local image links from the source folder or vault. Do not drop images, captions, lists, links, quotations, or text. If an image is unavailable, leave a clear image placeholder at its original position rather than moving surrounding content.
2. **Apply the user's layout profile.** Make formatting decisions from the article's structure and the rules below. Keep the original wording, facts, order, and paragraph structure. Do not split, merge, or rewrite paragraphs to make styling easier. Do not over-style: use orange emphasis sparingly and only on a short phrase or meaningful clause.
3. **Load the formatted article into the local editor.** Use the existing editor at `/Users/haolinwong/Documents/GitHub/Huang_ob/06_输/00_橙橘排版器/wechat-editor/dist/index.html`; do not create or deploy a website. Keep the existing three-column editor and phone preview. Use local images where available. Show the completed article in the editor and leave the local editor open for the user when the available browser workflow allows it.
4. **Review the result.** Confirm that the title, text, images, captions, and heading order match the source. Check the editor preview and the phone preview, especially the first section and the later article sections. If a display or browser restriction prevents opening the local editor, finish preparing the local editor file and tell the user which page to refresh; do not claim it is open.
5. **Report briefly.** Say which source was formatted, where it is displayed, and mention any missing images or unresolved source ambiguity. Do not ask the user to confirm routine styling choices.

## Formatting profile

- **Body:** 15px, dark gray, 1px letter spacing, line-height 1.85, justified; paragraphs have 20px bottom spacing. Preserve existing paragraph boundaries.
- **Section headings:** use the existing standalone heading style: black bold text at 20px, with a 4px orange vertical bar on the left, 10px left inset, 36px top spacing, and 20px bottom spacing. The orange bar and title must align on the same line. Apply this style only to a standalone heading line or when the whole paragraph is designated as a heading. Do not extract a few words from the start or middle of a body paragraph and turn them into a heading; that breaks the paragraph structure. If the intended heading is ambiguous, retain the text as body copy.
- **Orange emphasis:** orange and bold. Select only a short phrase or a meaningful clause within a longer sentence; never emphasize an entire long paragraph or sentence by default. Use a few clear highlights, not one in every paragraph. Preserve all original wording.
- **Image captions / gray annotations:** 12px gray, centered. Keep them directly associated with the image or selected text. Centering must not change paragraph line-height or margins.
- **Images:** retain original order and placement, full content width, natural aspect ratio, and no rounded corners. Do not invent image descriptions. Keep explicit image placeholders where the source calls for an image that is not available.
- **Phone preview:** match the reference image's 1220:2816 portrait ratio. The phone stays fixed in its preview pane; do not add scroll-position calibration or editor-to-phone scroll synchronization.
- **Style actions:** selected text becomes the chosen style; toolbar actions must not insert duplicate content. Applying body style to a whole paragraph restores the body typography and original paragraph spacing. Applying gray annotation centers the containing paragraph while preserving its line-height and spacing.

## Source handling

- Obsidian Markdown: follow embeds and relative image paths; copy needed image assets into the local editor's article assets area only when required for preview, without modifying or moving the source note.
- HTML/MHTML: preserve DOM reading order, image references, captions, links, and meaningful inline emphasis. Ignore browser chrome and clipping metadata.
- Pasted text plus images: retain the supplied sequence. Keep a placeholder where the user explicitly indicates an image should be inserted later.
- Use the local editor's current article-loading mechanism and existing formatting rules. Do not overwrite unrelated editor code, other drafts, or the source article.
