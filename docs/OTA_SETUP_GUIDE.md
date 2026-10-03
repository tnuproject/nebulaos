# Guida Configurazione Repository Aggiornamenti OTA per NebulaOS

Questa guida spiega come configurare la repository GitHub [https://github.com/tnuproject/updates/](https://github.com/tnuproject/updates/) affinché i pacchetti di aggiornamento (es. nuove versioni delle app, patch di sistema o il passaggio da NebulaOS 26 a 27) vengano rilevati automaticamente da **GNOME Software** (l'App Store / Centro Aggiornamenti) e dalle Impostazioni di sistema.

---

## 1. Come funziona l'ecosistema di aggiornamento GNOME / Debian

1. **NebulaOS include già la sorgente APT preconfigurata**:
   In `/etc/apt/sources.list.d/nebula-updates.list`:
   ```apt
   deb [trusted=yes] https://tnuproject.github.io/updates/ ./
   ```
2. **PackageKit & GNOME Software**:
   GNOME Software monitora periodicamente i repository APT in background. Quando carichi un nuovo pacchetto `.deb` (es. `nebula-desktop_27.0_all.deb`) con versione superiore a quella installata, GNOME Software mostra una notifica di aggiornamento di sistema e permette all'utente di aggiornare con un clic su **"Scarica e Installa"**.

---

## 2. Configurazione della Repository GitHub (`tnuproject/updates`)

Per far funzionare il repository come sorgente APT senza dover noleggiare server dedicati, usiamo **GitHub Pages** e una **GitHub Action** automatica che crea i file di indice APT (`Packages.gz` e `Release`) ad ogni push o release.

### Passo A: Attivare GitHub Pages sul repository
1. Vai su GitHub: [https://github.com/tnuproject/updates/settings/pages](https://github.com/tnuproject/updates/settings/pages)
2. Sotto **Build and deployment** > **Source**, seleziona:
   - **Deploy from a branch**
   - Branch: `gh-pages` (oppure `main` / `root`)
3. L'URL pubblico diventerà: `https://tnuproject.github.io/updates/`

---

### Passo B: Creare il Workflow GitHub Actions per l'aggiornamento automatico degli indici

Crea il file `.github/workflows/apt-repo.yml` all'interno della repo `tnuproject/updates`:

```yaml
name: Generate APT Repository

on:
  push:
    branches:
      - main
    paths:
      - '**.deb'
  release:
    types: [published]
  workflow_dispatch:

permissions:
  contents: write
  pages: write
  id-token: write

jobs:
  build-apt-repo:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install APT repository tools
        run: |
          sudo apt-get update
          sudo apt-get install -y dpkg-dev gzip

      - name: Scan deb packages and build APT indexes
        run: |
          # Genera il file di indice Packages e Packages.gz
          dpkg-scanpackages -m . /dev/null > Packages
          gzip -9c Packages > Packages.gz

          # Genera il file Release
          cat << 'EOF' > Release
          Origin: NebulaOS
          Label: NebulaOS Official Updates
          Suite: stable
          Codename: apollo
          Architectures: amd64 all
          Components: main
          Description: NebulaOS Official OTA Package Updates
          Date: $(date -Ru)
          EOF

      - name: Deploy to gh-pages branch
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: .
          publish_branch: gh-pages
```

---

## 3. Come pubblicare un aggiornamento (Es. da NebulaOS 26 a 27)

1. **Crea il pacchetto `.deb` aggiornato** con la nuova versione nel file `debian/control`:
   ```control
   Package: nebula-desktop
   Version: 27.0-1
   Architecture: all
   Maintainer: NebulaOS Team
   Description: NebulaOS Desktop Environment and system configurations
   ```
2. **Carica il file `.deb` nella repository** `tnuproject/updates` (nella root o cartella debs) e fai `git push`:
   - La GitHub Action si attiva in automatico.
   - Crea `Packages.gz` e `Release`.
   - Pubblica l'indice su `https://tnuproject.github.io/updates/`.
3. **Sulle macchine NebulaOS degli utenti**:
   - GNOME Software verificherà la presenza del nuovo pacchetto.
   - Comparirà l'avviso di sistema: *"Aggiornamento di sistema disponibile: NebulaOS 27.0"*.
   - Cliccando su **Aggiorna**, il sistema si aggiorna in modo fluido e trasparente!
