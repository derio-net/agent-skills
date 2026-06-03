---
name: homepage-icon-finder
description: Use when setting icon values for Homepage (gethomepage.dev) dashboard services, or when homepage icons appear broken/missing. Triggers on homepage YAML configs with icon fields.
---

# Homepage Icon Finder

Find and verify icons for [Homepage](https://gethomepage.dev) dashboard service entries.

## Icon Sources & Prefixes

| Prefix | Source | Example | Search URL |
|--------|--------|---------|------------|
| *(none)* | [Dashboard Icons](https://github.com/walkxcode/dashboard-icons) | `argo-cd` | Fetch `https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/tree.json` |
| `si-` | [Simple Icons](https://simpleicons.org) | `si-github` | Fetch `https://raw.githubusercontent.com/simple-icons/simple-icons/master/slugs.md` |
| `sh-` | [selfh.st Icons](https://selfh.st/icons/) | `sh-nextcloud` | Fetch `https://raw.githubusercontent.com/selfhst/icons/refs/heads/main/index.json` |
| `mdi-` | [Material Design Icons](https://materialdesignicons.com) | `mdi-flask-outline` | Search `https://pictogrammers.com/library/mdi/` |
| URL | Direct image | `https://example.com/logo.png` | N/A |
| `/icons/` | Local mount | `/icons/myapp.png` | Mount to `/app/public/icons` in container |

## Lookup Procedure

1. **Search Dashboard Icons first** (highest quality, purpose-built for dashboards):
   ```
   WebFetch https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/tree.json
   → search for service name and common aliases
   ```
   Names use hyphens: `argo-cd`, `home-assistant`, `pi-hole`, `visual-studio-code`

2. **Try Simple Icons** if not found (brand logos):
   ```
   WebFetch https://raw.githubusercontent.com/simple-icons/simple-icons/master/slugs.md
   → search for brand name
   ```
   Slugs are lowercase, no hyphens: `argo`, `kubernetes`, `grafana`

3. **Try selfh.st** for self-hosted app icons:
   ```
   WebFetch https://raw.githubusercontent.com/selfhst/icons/refs/heads/main/index.json
   → search for app name
   ```

4. **Fall back to MDI** for generic icons: `mdi-server`, `mdi-kubernetes`, `mdi-robot`

5. **Last resort**: Direct URL to the project's logo from their GitHub/website

## Color Customization

For `si-` and `mdi-` icons, append hex color: `si-github-#181717`, `mdi-server-#4CAF50`

## Common Gotchas

| Service | Wrong | Right | Why |
|---------|-------|-------|-----|
| ArgoCD | `argocd`, `si-argocd` | `argo-cd` (dashboard) or `si-argo` (simple) | Dashboard Icons uses hyphenated name; Simple Icons slug is just `argo` |
| Pi-hole | `pihole` | `pi-hole` | Dashboard Icons uses hyphen |
| Home Assistant | `homeassistant` | `home-assistant` | Dashboard Icons uses hyphen |
| Sidero Omni | `sidero-omni`, `si-sidero` | `/icons/sidero-omni.png` (local mount) | Not in any icon registry; committed to `docs/icons/`, copied into container by role |
| KubeVirt | `kubevirt`, `si-kubevirt` | `https://raw.githubusercontent.com/kubevirt/community/main/logo/KubeVirt_icon.svg` | Not in any icon registry; use direct GitHub URL |

## Verification

After setting an icon, the only true verification is loading the Homepage dashboard. However, you can pre-verify by checking the icon exists in the source registry using the search URLs above.
