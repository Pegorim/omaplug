# Proposal: make installed software visible in Omarchy

Omarchy can install packages and shell plugins, but answering “what is installed, and what changed?” still takes several commands. Omaplug brings those answers into a single native bar panel.

The proposed feature is deliberately small: searchable package and plugin inventories, expandable details, and grouped change history. It uses existing shell controls and theme tokens. It complements the update indicator without introducing another package manager or an online catalogue.

Package data comes from pacman and its log. Plugin enabled state comes from the shell registry. A shared shell service detects plugin changes and stores history locally. The interface distinguishes recorded package transactions from observed plugin changes and does not invent installation dates.

The implementation is a standalone MIT-licensed plugin, with no changes to packaged Omarchy files or public shell APIs. A future upstream integration could adopt a first-party ID and reuse the panel and collector. That integration is not included in this local delivery.

Before an upstream submission, confirm the current repository's contribution guidance, review whether this belongs in the default bar or an optional plugin, and address the installed shell's compiled-component reload limitation if it remains reproducible upstream. Validate against the then-current development branch.

The checkout includes collector tests, model tests, and screenshots. This document is published here as a draft only. No upstream proposal, pull request, or message has been submitted to the Omarchy maintainers.
