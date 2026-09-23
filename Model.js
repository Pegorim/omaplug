function matches(item, query) {
  return JSON.stringify(item).toLowerCase().indexOf(query.trim().toLowerCase()) !== -1
}

function rows(snapshot, tab, filter, query) {
  var items = snapshot[tab] || []
  return items.filter(function(item) {
    if (!matches(item, query)) return false
    if (tab === "packages") {
      if (filter === "Updates") return !!item.update
      if (filter === "Explicit") return item.explicit
      if (filter === "Dependencies") return !item.explicit
      if (filter === "Foreign") return item.origin === "Foreign"
    } else if (tab === "plugins") {
      if (filter === "Updates") return item.update && item.update.state === "available"
      if ((filter === "Enabled" || filter === "On")) return item.enabled
      if ((filter === "Disabled" || filter === "Off")) return !item.enabled
      if ((filter === "User" || filter === "Yours")) return !item.firstParty
    } else if (tab === "discover") {
      if (filter === "Installable") return item.installable && !item.installed
      if (filter === "Installed") return item.installed
      if (filter === "Verified") return item.verification === "Snapshot verified"
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

function discover(catalog, installed) {
  var ids = {}
  installed.forEach(function(item) { ids[item.id] = true })
  return (catalog.plugins || []).map(function(item) {
    return Object.assign({}, item, { installed: Object.prototype.hasOwnProperty.call(ids, item.id) })
  })
}

function subtitle(item, tab) {
  if (tab === "discover") return item.description || (item.category + " · " + item.author)
  if (tab === "packages") return item.description
  if (tab === "plugins") return item.description || ((item.firstParty ? "Bundled" : "User installed") + " · " + (item.kinds || []).join(", "))
  return date(item.at) + (item.kind === "plugins" ? " · Detected" : item.complete ? " · Completed" : " · Completion unconfirmed")
}

function details(item, tab) {
  if (tab === "discover") return item.description + "\n\n" + item.author + " · " + item.category + " · " + item.version
    + "\n" + item.repo + "\n" + item.verification
    + (item.installNote ? "\n\n" + item.installNote : "")
  if (tab === "packages") return item.description + "\n\n" + item.version + " · " + item.architecture
    + "\n" + item.origin + " · " + (item.explicit ? "Explicitly installed" : "Dependency")
    + "\nInstalled size: " + item.size + "\nLast installed: " + item.installedAt
    + (item.origin === "Foreign" ? "\nForeign packages may come from AUR or a local package file." : "")
  if (tab === "plugins") return (item.description || item.name) + "\n\n" + item.id
    + "\nVersion: " + item.version + (item.revision ? "\nRevision: " + item.revision.slice(0, 12) : "")
    + "\n" + (item.enabled ? "Enabled" : "Disabled") + " · " + (item.firstParty ? "Bundled" : "User installed")
    + "\n" + item.path + "\nInstallation date: unknown"
  return (item.changes || []).map(changeText).join("\n\n")
}

function installedPlugins(items) {
  return items.map(function(item) {
    return Object.assign({}, item, {group: item.firstParty ? "Included with Omarchy" : "Your plugins"})
  }).sort(function(a, b) {
    return Number(!!a.firstParty) - Number(!!b.firstParty) || a.name.localeCompare(b.name)
  })
}
function toggleBlock(item) {
  if (item.id === "mateus.omaplug") return "Omaplug stays on while you manage plugins"
  if (item.canDisable !== true || (item.kinds || []).indexOf("bar") !== -1) return "Required by the shell"
  return ""
}

function withUpdates(items, updates, tab) {
  var map = {}
  var groups = tab === "packages" ? [updates.repositories, updates.aur] : [updates.plugins]
  groups.forEach(function(group) {
    if (!group) return
    var data = group.state === "ok" ? group : group.lastSuccess
    if (!data) return
    var stale = group.state !== "ok" || Date.now() / 1000 - data.checkedAt >= 900
    ;(data.items || []).forEach(function(item) { map[item.id] = Object.assign({}, item, {stale: stale}) })
  })
  return items.map(function(item) { return Object.assign({}, item, {update: map[item.id] || null}) })
}
function updateSummary(group, noun, now) {
  if (!group) return noun + ": Not checked"
  if (group.state !== "ok") return noun + ": Check failed"
  var count = (group.items || []).length
  return noun + ": " + (count ? count + " update" + (count === 1 ? "" : "s") : "Up to date")
    + ((now || Date.now() / 1000) - group.checkedAt >= 900 ? " (stale)" : "")
}

function updateDetails(updates) {
  return ["repositories", "aur", "omarchy", "plugins"].map(function(key) {
    var g = updates[key]
    if (!g) return key + ": Not checked"
    var last = g.state === "ok" ? g.checkedAt : g.lastSuccess && g.lastSuccess.checkedAt
    return key + ": " + (g.error || g.note || "Checked") + " · Last success: " + date(last)
  }).join("\n")
}
