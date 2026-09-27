# mtlm-router.intrane.fr — landing source

These files are the landing page as served by superlandings-go on the host
(site slug `mtlm-router`, one directory per version under
`~/.superlandings/sites/mtlm-router/vN`). Until 2026-09-27 the host copy was
the only one; this folder is now the source of truth.

| file | what |
|---|---|
| `layout.html` | shared shell: nav, footer, and the whole "signal box" theme |
| `index.html` / `fr.html` | English / French page bodies (`{{>layout "layout.html"}}`) |
| `*.html.data.json` | per-language template values (`{{.title}}`, `{{.root}}`, nav labels, links) |

## Styling

The page bodies keep their Tailwind utility classes. The theme lives in
`layout.html`: the Tailwind CDN palette is remapped in `tailwind.config`
(`gray-950` is the paper, `gray-200` the ink, `white` the ink, `cyan-*` enamel
blue, `green`/`amber` the signals), code blocks become dark "departure board"
panels via `div:has(> pre)`, and the live demo's result cells (`#pg-out`) are
split-flap tiles. Adding content: use the existing classes and it inherits the
theme.

The live demo calls `https://api.mtlm-router.intrane.fr/demo/route`, which only
CORS-allows the production origin, and the audit form posts to the bkn `forms`
hook (form `mtlm-leads`). Keep the element ids (`pg-*`, `lead-*`) — the inline
script depends on them.

## Deploy

Always as a new version, so the previous one stays one command away:

```sh
scp site/{layout.html,index.html,fr.html,*.data.json} <host>:/tmp/mtlm-vN/
# on the host
cd /tmp/mtlm-vN
sl-cli site version create mtlm-router --version vN --comment "..."
for f in layout.html index.html fr.html index.html.data.json fr.html.data.json; do
  sl-cli site write mtlm-router vN "$f" --content "$(cat "$f")"
done
sl-cli site version switch mtlm-router vN     # rollback: switch back to vN-1
```
