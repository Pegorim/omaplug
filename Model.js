function matches(item, query) {
  return JSON.stringify(item).toLowerCase().indexOf(query.trim().toLowerCase()) !== -1
}

function rows(snapshot, tab, filter, query) {
  var items = snapshot[tab] || []
  return items.filter(function(item) {
    if (!matches(item, query)) return false
    if (tab === "packages") {
      if (filter === "Explicit") return item.explicit
      if (filter === "Dependencies") return !item.explicit
      if (filter === "Foreign") return item.origin === "Foreign"
    } else if (tab === "plugins") {
      if (filter === "Enabled") return item.enabled
      if (filter === "Disabled") return !item.enabled
      if (filter === "User") return !item.firstParty
    } else if (filter !== "All") return item.kind === filter.toLowerCase()
    return true
  })
}

function date(timestamp) {
  return timestamp ? new Date(timestamp * 1000).toLocaleString(Qt.locale(), "dd MMM yyyy, HH:mm") : "Not yet checked"
}

function changeText(change) {
  var versions = change.old && change.new ? change.old + " → " + change.new : change.new || change.old || ""
  return change.name + " · " + change.action + (versions ? "\n" + versions : "")
}

function subtitle(item, tab) {
  if (tab === "packages") return item.description
  if (tab === "plugins") return (item.firstParty ? "Bundled" : "User installed") + " · " + item.kinds.join(", ")
  return date(item.at) + (item.kind === "plugins" ? " · Detected" : item.complete ? " · Completed" : " · Completion unconfirmed")
}

function details(item, tab) {
  if (tab === "packages") return item.description + "\n\n" + item.version + " · " + item.architecture
    + "\n" + item.origin + " · " + (item.explicit ? "Explicitly installed" : "Dependency")
    + "\nInstalled size: " + item.size + "\nLast installed: " + item.installedAt
    + (item.origin === "Foreign" ? "\nForeign packages may come from AUR or a local package file." : "")
  if (tab === "plugins") return (item.description || item.name) + "\n\n" + item.id
    + "\nVersion: " + item.version + (item.revision ? "\nRevision: " + item.revision.slice(0, 12) : "")
    + "\n" + (item.enabled ? "Enabled" : "Disabled") + " · " + (item.firstParty ? "Bundled" : "User installed")
    + "\n" + item.path + "\nInstallation date: unknown"
  return item.changes.map(changeText).join("\n\n")
}
