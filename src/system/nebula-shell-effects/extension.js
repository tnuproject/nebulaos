/**
 * NebulaOS Shell Effects Extension
 * Implements:
 * 1. Fluid Wobbly Bubble Notification entering from top-right (EASE_OUT_BACK, 0->100% opacity at halfway point, large pill)
 * 2. Dynamic Top Bar: 0% opacity by default, becomes black when an app window is open, transparent when closed
 * 3. Launchpad (App Grid) animation rising from the bottom dock upwards
 * 4. App Window opening animation expanding outward from top-left
 * 5. Elevated floating dock (36px detached from bottom edge)
 * 6. Smooth Fade-Out to Black on Shutdown / Reboot
 * 7. Unified Lockscreen & GDM Login Screen:
 *    - Huge bold clock + date + padlock icon (lock_symbolic.svg)
 *    - Circular white avatar with tactile button "squish" animation
 *    - Multi-user switching by clicking the avatar
 *    - Capsule pill password entry with play/arrow submit button
 */

const { Clutter, GLib, St, Meta, Shell, AccountsService, GnomeDesktop, Gio, GObject, Pango } = imports.gi;
const Main = imports.ui.main;
const MessageTray = imports.ui.messageTray;
const Dash = imports.ui.dash;

let UnlockDialog = null;
try {
    UnlockDialog = imports.ui.unlockDialog;
} catch (e) {}

let LoginDialog = null;
try {
    LoginDialog = imports.gdm.loginDialog;
} catch (e) {}

let AuthPrompt = null;
try {
    AuthPrompt = imports.gdm.authPrompt;
} catch (e) {}

let UserWidget = null;
try {
    UserWidget = imports.ui.userWidget;
} catch (e) {}

let QuickSettings = null;
try {
    QuickSettings = imports.ui.quickSettings;
} catch (e) {}

let DND = null;
try {
    DND = imports.ui.dnd;
} catch (e) {}

let _petalDropToggle = null;
let _petalDropOverlay = null;
let _petalDropIndicator = null;
let _petalDropWinSignal = null;

let _origShowBanner = null;
let _origHideBanner = null;
let _origUpdateIcon = null;
let _origShowAppsIconInit = null;
let _overviewShowingId = null;
let _overviewHidingId = null;
let _windowCreatedId = null;
let _switchWorkspaceId = null;
let _panelWindowSignals = [];

let _origBannerBinXAlign = null;
let _origBannerBinYAlign = null;
let _origBannerBinTranslationX = 0;
let _origUnlockDialogInit = null;
let _origUnlockDialogSetTransitionProgress = null;
let _origUnlockDialogShowClock = null;
let _origUnlockDialogShowPrompt = null;
let _origUnlockDialogEnsureAuthPrompt = null;
let _origUnlockDialogLayoutAllocate = null;
let _origLoginDialogInit = null;
let _origLoginDialogShowUserList = null;
let _origLoginDialogOnReset = null;
let _origLoginDialogGetCenterActorAllocation = null;
let _origLoginDialogVfuncAllocate = null;
let _origLoginDialogStartSession = null;
let _origAuthPromptInit = null;
let _origAuthPromptSetUser = null;
let _origAuthPromptReset = null;
let _origAuthPromptInitInputRow = null;
let _origAuthPromptActivateNext = null;
let _origAuthPromptOnVerificationComplete = null;
let _origAuthPromptFinish = null;
let _origAuthPromptUpdateEntry = null;
let _origUnlockDialogDestroy = null;
let _origUserWidgetLabelInit = null;
let _sessionUpdatedId = null;

function getValidUser() {
    try {
        let userManager = AccountsService.UserManager.get_default();
        let curUserName = GLib.get_user_name();
        let user = null;
        if (curUserName && curUserName !== 'root' && curUserName !== 'Debian-gdm') {
            user = userManager.get_user(curUserName);
        }
        if (!user || (!user.is_loaded && !user.user_name)) {
            let users = userManager.list_users().filter(u => !u.is_system_account());
            if (users.length > 0) user = users[0];
        }
        if (!user) {
            user = userManager.get_user('nebula');
        }
        return user;
    } catch (e) {
        return null;
    }
}

function updateDateMenuVisibility() {
    try {
        let isLock = (Main.sessionMode && (Main.sessionMode.currentMode === 'unlock-dialog' || Main.sessionMode.currentMode === 'gdm'));
        if (Main.panel && Main.panel.statusArea && Main.panel.statusArea.dateMenu) {
            Main.panel.statusArea.dateMenu.visible = !isLock;
        }
    } catch (e) {}
}

function applyLockscreenBackground(actor) {
    if (!actor) return;
    try {
        let bgStyle = 'background: #000000 url("file:///usr/share/backgrounds/nebula/plains-default.svg") no-repeat center !important; background-size: cover !important;';
        actor.set_style(bgStyle);
    } catch (e) {}
}

// Clock Widget for Lockscreen & GDM (Centered, Huge Time, Padlock, No Date)
const NebulaLockClock = GObject.registerClass(
class NebulaLockClock extends St.BoxLayout {
    _init() {
        super._init({
            vertical: true,
            style_class: 'nebula-lock-container',
            x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.CENTER,
            x_expand: true,
            visible: true,
            opacity: 255,
            reactive: false,
        });
        this.set_style('width: 100%; min-height: 180px;');

        // Padlock icon centered above time
        this._lockIcon = new St.Icon({
            icon_name: 'channel-secure-symbolic',
            fallback_icon_name: 'system-lock-screen-symbolic',
            icon_size: 28,
            style_class: 'nebula-lock-icon',
            x_align: Clutter.ActorAlign.CENTER,
            visible: true,
            opacity: 255,
        });
        this.add_child(this._lockIcon);

        // Huge bold clock time (e.g. 12:00) strictly centered and never ellipsized
        this._timeLabel = new St.Label({
            style_class: 'nebula-lock-time',
            x_align: Clutter.ActorAlign.CENTER,
            x_expand: true,
            visible: true,
            opacity: 255,
        });
        if (this._timeLabel.clutter_text) {
            this._timeLabel.clutter_text.set_line_alignment(Pango.Alignment.CENTER);
            this._timeLabel.clutter_text.set_ellipsize(Pango.EllipsizeMode.NONE);
            this._timeLabel.clutter_text.set_line_wrap(false);
            this._timeLabel.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
            this._timeLabel.clutter_text.line_wrap = false;
        }
        this._timeLabel.set_style('width: 100%; text-align: center; color: #ffffff;');
        this.add_child(this._timeLabel);

        // Date label below time (e.g. "Sun, 22 September")
        this._dateLabel = new St.Label({
            style_class: 'nebula-lock-date',
            x_align: Clutter.ActorAlign.CENTER,
            x_expand: true,
            visible: true,
            opacity: 255,
        });
        if (this._dateLabel.clutter_text) {
            this._dateLabel.clutter_text.set_line_alignment(Pango.Alignment.CENTER);
            this._dateLabel.clutter_text.set_ellipsize(Pango.EllipsizeMode.NONE);
            this._dateLabel.clutter_text.set_line_wrap(false);
            this._dateLabel.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
            this._dateLabel.clutter_text.line_wrap = false;
        }
        this._dateLabel.set_style('width: 100%; text-align: center; color: rgba(255, 255, 255, 0.92);');
        this.add_child(this._dateLabel);

        this._wallClock = new GnomeDesktop.WallClock({ time_only: true });
        this._clockSignal = this._wallClock.connect('notify::clock', this._updateClock.bind(this));
        this._updateClock();

        this.connect('destroy', () => {
            if (this._clockSignal && this._wallClock) {
                this._wallClock.disconnect(this._clockSignal);
                this._clockSignal = null;
            }
        });
    }

    _updateClock() {
        let now = new Date();
        let hours = now.getHours().toString().padStart(2, '0');
        let mins = now.getMinutes().toString().padStart(2, '0');
        this._timeLabel.text = `${hours}:${mins}`;

        try {
            let weekday = now.toLocaleDateString(undefined, { weekday: 'short' });
            weekday = weekday.charAt(0).toUpperCase() + weekday.slice(1);
            let day = now.getDate();
            let month = now.toLocaleDateString(undefined, { month: 'long' });
            month = month.charAt(0).toUpperCase() + month.slice(1);
            this._dateLabel.text = `${weekday}, ${day} ${month}`;
        } catch (e) {
            this._dateLabel.text = now.toLocaleDateString();
        }
    }
});


// Avatar Squish Animation & Multi-User Switch for Lockscreen & GDM
function setupAvatarSquish(userWidget, authPromptInstance) {
    if (!userWidget || userWidget._nebulaSquishHooked) return;
    userWidget._nebulaSquishHooked = true;

    let targetActor = userWidget._avatar || null;
    if (!targetActor) {
        for (let child of userWidget.get_children()) {
            if (child.has_style_class_name && (child.has_style_class_name('user-icon') || child.has_style_class_name('user-avatar'))) {
                targetActor = child;
                break;
            }
        }
    }
    if (!targetActor) targetActor = userWidget;

    targetActor.reactive = true;
    targetActor.can_focus = true;
    targetActor.track_hover = true;
    targetActor.set_pivot_point(0.5, 0.5);

    let clickAction = new Clutter.ClickAction();
    clickAction.connect('clicked', () => {
        targetActor.ease({
            scale_x: 1.12,
            scale_y: 0.80,
            duration: 100,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => {
                targetActor.ease({
                    scale_x: 1.0,
                    scale_y: 1.0,
                    duration: 260,
                    mode: Clutter.AnimationMode.EASE_OUT_BACK
                });
            }
        });

        try {
            let userManager = AccountsService.UserManager.get_default();
            let allUsers = userManager.list_users().filter(u => !u.is_system_account() && u.is_loaded);
            if (allUsers.length > 1 && authPromptInstance) {
                let currentName = authPromptInstance._userName ||
                    (authPromptInstance._user ? authPromptInstance._user.get_user_name() : '');
                let curIdx = allUsers.findIndex(u => u.get_user_name() === currentName);
                let nextIdx = (curIdx + 1) % allUsers.length;
                let nextUser = allUsers[nextIdx];

                authPromptInstance.setUser(nextUser);
                authPromptInstance._userName = nextUser.get_user_name();
                authPromptInstance._user = nextUser;

                if (authPromptInstance._userVerifier) {
                    authPromptInstance._userVerifier.cancel();
                    authPromptInstance._userVerifier.begin(nextUser.get_user_name(), new Gio.Cancellable());
                } else if (authPromptInstance.begin) {
                    try {
                        authPromptInstance.reset();
                    } catch (e) {}
                    try {
                        authPromptInstance.begin({ userName: nextUser.get_user_name() });
                    } catch (e) {}
                }

                if (authPromptInstance._entry) {
                    authPromptInstance._entry.set_text('');
                    authPromptInstance._entry.grab_key_focus();
                }

                GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                    let newChild = authPromptInstance._userWell ? authPromptInstance._userWell.get_child() : null;
                    if (newChild) setupAvatarSquish(newChild, authPromptInstance);
                    return GLib.SOURCE_REMOVE;
                });
            }
        } catch (e) {
            log(`[Nebula] User switch error: ${e}`);
        }
    });

    targetActor.add_action(clickAction);
}

function elevateDockActors() {
    // Dock elevation is handled cleanly via stylesheet.css
}

function updatePanelOpacity() {
    if (!Main.panel) return;
    try {
        if (Main.overview && Main.overview.visible) {
            Main.panel.remove_style_class_name('panel-opaque');
            return;
        }

        const ws = global.workspace_manager ? global.workspace_manager.get_active_workspace() : null;
        if (!ws) return;

        let hasOpenApp = false;
        const windows = ws.list_windows();
        for (let w of windows) {
            if (w.get_window_type() === Meta.WindowType.NORMAL && !w.minimized && !w.is_skip_taskbar()) {
                hasOpenApp = true;
                break;
            }
        }

        if (hasOpenApp) {
            Main.panel.add_style_class_name('panel-opaque');
        } else {
            Main.panel.remove_style_class_name('panel-opaque');
        }
    } catch (e) {}
}

function watchWindow(metaWindow) {
    if (!metaWindow || metaWindow.get_window_type() !== Meta.WindowType.NORMAL) return;
    let sigMin = metaWindow.connect('notify::minimized', () => updatePanelOpacity());
    let sigUnman = metaWindow.connect('unmanaged', () => {
        try {
            metaWindow.disconnect(sigMin);
            metaWindow.disconnect(sigUnman);
        } catch (e) {}
        updatePanelOpacity();
    });
    _panelWindowSignals.push([metaWindow, sigMin, sigUnman]);
}

// ─── Nebula Spotlight ─────────────────────────────────────────────────────────
let _spotlight = null;
let _spotlightKeybindingId = null;

const NebulaSpotlight = GObject.registerClass(
class NebulaSpotlight extends St.Widget {
    _init() {
        super._init({
            name: 'nebula-spotlight',
            layout_manager: new Clutter.BinLayout(),
            reactive: true,
            visible: false,
            opacity: 0,
        });

        // Full-screen transparent backdrop (click to dismiss)
        this._backdrop = new St.Widget({
            style: 'background: transparent;',
            reactive: true,
            x_expand: true,
            y_expand: true,
        });
        this._backdrop.connect('button-press-event', () => { this.hide(); return Clutter.EVENT_STOP; });
        this.add_child(this._backdrop);

        // Panel container centered on screen
        this._panel = new St.BoxLayout({
            vertical: true,
            style_class: 'nebula-spotlight-panel',
            style: `
                width: 620px;
                background-color: rgba(20, 20, 28, 0.88);
                border-radius: 18px;
                border: 1px solid rgba(255,255,255,0.14);
                box-shadow: 0 24px 64px rgba(0,0,0,0.70);
                padding: 0px;
            `,
            reactive: true,
            x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.START,
        });
        this._panel.connect('button-press-event', () => Clutter.EVENT_STOP); // don't dismiss on panel click
        this.add_child(this._panel);

        // Search entry row
        let entryRow = new St.BoxLayout({
            style: 'padding: 16px 20px; spacing: 12px;',
            x_expand: true,
        });
        this._panel.add_child(entryRow);

        let searchIcon = new St.Icon({
            icon_name: 'system-search-symbolic',
            icon_size: 20,
            style: 'color: rgba(255,255,255,0.55); margin-top: 4px;',
        });
        entryRow.add_child(searchIcon);

        this._entry = new St.Entry({
            style: `
                background: transparent;
                border: none;
                box-shadow: none;
                color: #ffffff;
                font-size: 20px;
                font-weight: 400;
                caret-color: #ffffff;
                min-width: 400px;
            `,
            hint_text: 'Search…',
            can_focus: true,
            x_expand: true,
        });
        entryRow.add_child(this._entry);

        // Separator
        let sep = new St.Widget({
            style: 'background-color: rgba(255,255,255,0.10); height: 1px; margin: 0;',
            x_expand: true,
        });
        this._panel.add_child(sep);

        // Results list
        this._resultsBox = new St.BoxLayout({
            vertical: true,
            style: 'padding: 8px 0px;',
            x_expand: true,
        });
        this._panel.add_child(this._resultsBox);

        // Key handler on entry
        this._entry.clutter_text.connect('text-changed', () => {
            this._doSearch(this._entry.get_text());
        });
        this._entry.clutter_text.connect('key-press-event', (actor, event) => {
            let sym = event.get_key_symbol();
            if (sym === Clutter.KEY_Escape) { this.hide(); return Clutter.EVENT_STOP; }
            if (sym === Clutter.KEY_Return || sym === Clutter.KEY_KP_Enter) {
                this._activateFirst();
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });

        this._appResults = [];
        this._doSearch('');
    }

    _doSearch(text) {
        // Clear old results
        this._resultsBox.destroy_all_children();
        this._appResults = [];

        let query = text.trim().toLowerCase();
        let appSys = Shell.AppSystem.get_default();
        let allApps = appSys.get_installed();

        let matched = allApps.filter(app => {
            if (app.get_nodisplay()) return false;
            let name = (app.get_name() || '').toLowerCase();
            let desc = (app.get_description() || '').toLowerCase();
            if (!query) return true;
            return name.includes(query) || desc.includes(query);
        }).slice(0, 8);

        if (matched.length === 0 && !query) return;
        if (matched.length === 0) {
            let noRes = new St.Label({
                text: 'No results',
                style: 'color: rgba(255,255,255,0.40); font-size: 14px; padding: 12px 24px;',
            });
            this._resultsBox.add_child(noRes);
            return;
        }

        matched.forEach((app, idx) => {
            let row = new St.Button({
                style: `
                    background: transparent;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 16px;
                    margin: 2px 8px;
                `,
                reactive: true,
                can_focus: true,
                x_expand: true,
            });
            row.connect('notify::hover', () => {
                row.set_style(`
                    background: ${row.hover ? 'rgba(255,255,255,0.10)' : 'transparent'};
                    border: none;
                    border-radius: 10px;
                    padding: 8px 16px;
                    margin: 2px 8px;
                `);
            });

            let rowBox = new St.BoxLayout({ style: 'spacing: 14px;', x_expand: true });
            row.set_child(rowBox);

            // App icon
            let icon = null;
            try { icon = app.create_icon_texture(32); } catch(e) {}
            if (!icon) icon = new St.Icon({ icon_name: 'application-x-executable', icon_size: 32 });
            rowBox.add_child(icon);

            // App name
            let label = new St.Label({
                text: app.get_name() || '',
                style: 'color: #ffffff; font-size: 15px; font-weight: 500; margin-top: 6px;',
                y_align: Clutter.ActorAlign.CENTER,
                x_expand: true,
            });
            rowBox.add_child(label);

            row.connect('clicked', () => {
                try { app.activate(); } catch(e) {}
                this.hide();
            });

            this._resultsBox.add_child(row);
            this._appResults.push({ row, app });
        });
    }

    _activateFirst() {
        if (this._appResults.length > 0) {
            try { this._appResults[0].app.activate(); } catch(e) {}
            this.hide();
        }
    }

    show() {
        if (!Main.uiGroup.contains(this)) {
            Main.uiGroup.add_child(this);
        }

        let monitor = Main.layoutManager.primaryMonitor;
        if (monitor) {
            this.set_position(monitor.x, monitor.y);
            this.set_size(monitor.width, monitor.height);
        }

        // Position panel at roughly 1/3 from top, centered horizontally
        if (monitor) {
            let panelX = Math.floor((monitor.width - 620) / 2);
            let panelY = Math.floor(monitor.height * 0.28);
            this._panel.set_position(panelX, panelY);
        }

        this._entry.set_text('');
        this._doSearch('');
        this.visible = true;
        this.ease({
            opacity: 255,
            duration: 200,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
        });
        GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            try { this._entry.grab_key_focus(); } catch(e) {}
            return GLib.SOURCE_REMOVE;
        });
    }

    hide() {
        this.ease({
            opacity: 0,
            duration: 160,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => { this.visible = false; },
        });
    }
});

function togglePetalDropOverlay() {
    try {
        let petaldropBin = '/usr/bin/petaldrop';
        if (GLib.file_test(petaldropBin, GLib.FileTest.EXISTS)) {
            GLib.spawn_command_line_async('/usr/bin/petaldrop --toggle');
            return;
        }
    } catch (e) {
        log(`[Nebula] PetalDrop launch error: ${e}`);
    }

    if (_petalDropOverlay) {
        try {
            _petalDropOverlay.destroy();
        } catch (e) {}
        _petalDropOverlay = null;
        return;
    }
    showPetalDropOverlay();
}

function showPetalDropOverlay() {
    if (_petalDropOverlay) {
        try { _petalDropOverlay.destroy(); } catch (e) {}
        _petalDropOverlay = null;
    }

    let overlay = new St.BoxLayout({
        style_class: 'petaldrop-overlay',
        vertical: true,
        reactive: true,
        can_focus: true,
        track_hover: true,
    });

    let monitor = Main.layoutManager.primaryMonitor;
    let cardWidth = 440;
    let startX = monitor ? (monitor.x + monitor.width - cardWidth - 28) : 50;
    let startY = monitor ? (monitor.y + (Main.panel ? Main.panel.height : 32) + 16) : 50;
    overlay.set_position(startX, startY);
    overlay.set_width(cardWidth);

    // 1. Header Box
    let headerBox = new St.BoxLayout({
        vertical: false,
        x_expand: true,
        y_align: Clutter.ActorAlign.CENTER,
    });

    let shareIcon = new St.Icon({
        icon_name: 'document-send-symbolic',
        icon_size: 20,
        style: 'color: #3584e4; margin-right: 10px;',
    });
    headerBox.add_child(shareIcon);

    let titleLabel = new St.Label({
        text: 'Petal Drop',
        style_class: 'petaldrop-title',
        y_align: Clutter.ActorAlign.CENTER,
    });
    headerBox.add_child(titleLabel);

    // Spacer
    let spacer = new St.Widget({ x_expand: true });
    headerBox.add_child(spacer);

    // Close Button 'X'
    let closeBtn = new St.Button({
        style_class: 'petaldrop-close-btn',
        can_focus: true,
        reactive: true,
        track_hover: true,
    });
    let closeIcon = new St.Icon({
        icon_name: 'window-close-symbolic',
        icon_size: 14,
    });
    closeBtn.set_child(closeIcon);
    closeBtn.connect('clicked', () => {
        if (_petalDropOverlay) {
            _petalDropOverlay.ease({
                opacity: 0,
                duration: 200,
                mode: Clutter.AnimationMode.EASE_OUT_QUAD,
                onComplete: () => {
                    if (_petalDropOverlay) {
                        try { _petalDropOverlay.destroy(); } catch (e) {}
                        _petalDropOverlay = null;
                    }
                }
            });
        }
    });
    headerBox.add_child(closeBtn);
    overlay.add_child(headerBox);

    // Content container where views swap
    let contentBin = new St.BoxLayout({
        vertical: true,
        x_expand: true,
        y_expand: true,
    });
    overlay.add_child(contentBin);

    // Function to render View 1 (Initial Drop Zone)
    let renderDropZoneView = () => {
        contentBin.destroy_all_children();

        let dropZone = new St.BoxLayout({
            style_class: 'petaldrop-dropzone',
            vertical: true,
            x_align: Clutter.ActorAlign.FILL,
            y_align: Clutter.ActorAlign.CENTER,
            x_expand: true,
            reactive: true,
            can_focus: true,
        });

        let dropIcon = new St.Icon({
            icon_name: 'folder-drag-accept-symbolic',
            icon_size: 46,
            style: 'color: #3584e4; margin-bottom: 8px;',
            x_align: Clutter.ActorAlign.CENTER,
        });
        dropZone.add_child(dropIcon);

        let promptLabel = new St.Label({
            text: 'Drop here the media you want to share via PetalDrop',
            style_class: 'petaldrop-prompt-text',
            x_align: Clutter.ActorAlign.CENTER,
        });
        if (promptLabel.clutter_text) {
            promptLabel.clutter_text.set_line_wrap(true);
            promptLabel.clutter_text.set_line_alignment(Pango.Alignment.CENTER);
        }
        dropZone.add_child(promptLabel);

        let subLabel = new St.Label({
            text: 'Offline & local Wi-Fi sharing with nearby NebulaOS & Android devices',
            style_class: 'petaldrop-sub-text',
            x_align: Clutter.ActorAlign.CENTER,
        });
        if (subLabel.clutter_text) {
            subLabel.clutter_text.set_line_wrap(true);
            subLabel.clutter_text.set_line_alignment(Pango.Alignment.CENTER);
        }
        dropZone.add_child(subLabel);

        // Browse button
        let browseBtn = new St.Button({
            label: 'Browse Files...',
            style_class: 'button',
            style: 'margin-top: 16px; border-radius: 9999px; padding: 6px 20px;',
            x_align: Clutter.ActorAlign.CENTER,
            can_focus: true,
            reactive: true,
        });
        browseBtn.connect('clicked', () => {
            try {
                let proc = Gio.Subprocess.new(
                    ['zenity', '--file-selection', '--title=PetalDrop - Select File to Share'],
                    Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
                );
                proc.communicate_utf8_async(null, null, (obj, res) => {
                    try {
                        let [, stdout] = obj.communicate_utf8_finish(res);
                        let path = (stdout || '').trim();
                        if (path && GLib.file_test(path, GLib.FileTest.EXISTS)) {
                            renderPeersView(path);
                        }
                    } catch (e) {}
                });
            } catch (e) {
                log(`[Nebula] File chooser spawn error: ${e}`);
            }
        });
        dropZone.add_child(browseBtn);

        // DND Delegate
        dropZone._delegate = {
            handleDragOver: () => (DND ? DND.DragMotionResult.COPY_DROP : 0),
            acceptDrop: (source, actor) => {
                let filePath = null;
                try {
                    if (source && source.file && source.file.get_path) {
                        filePath = source.file.get_path();
                    } else if (source && source.realFile && source.realFile.get_path) {
                        filePath = source.realFile.get_path();
                    } else if (source && source.get_uri) {
                        filePath = GLib.filename_from_uri(source.get_uri())[0];
                    } else if (actor && actor._delegate && actor._delegate.file) {
                        filePath = actor._delegate.file.get_path();
                    }
                } catch (e) {}

                if (filePath && GLib.file_test(filePath, GLib.FileTest.EXISTS)) {
                    renderPeersView(filePath);
                    return true;
                }
                return false;
            }
        };

        contentBin.add_child(dropZone);
    };

    // Function to render View 2 (Peers List & Send)
    let renderPeersView = (filePath) => {
        contentBin.destroy_all_children();

        let filename = GLib.path_get_basename(filePath);

        // File badge box
        let fileBadge = new St.BoxLayout({
            vertical: false,
            style: 'background-color: rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 10px 14px; margin-top: 14px; margin-bottom: 12px;',
            x_expand: true,
            y_align: Clutter.ActorAlign.CENTER,
        });
        let fileIcon = new St.Icon({
            icon_name: 'text-x-generic-symbolic',
            icon_size: 22,
            style: 'color: #3584e4; margin-right: 10px;',
        });
        fileBadge.add_child(fileIcon);

        let fileNameLabel = new St.Label({
            text: filename,
            style: 'font-weight: 600; color: #ffffff; font-size: 13px;',
            y_align: Clutter.ActorAlign.CENTER,
            x_expand: true,
        });
        if (fileNameLabel.clutter_text) {
            fileNameLabel.clutter_text.set_ellipsize(Pango.EllipsizeMode.MIDDLE);
        }
        fileBadge.add_child(fileNameLabel);

        let changeBtn = new St.Button({
            label: 'Change',
            style_class: 'button',
            style: 'font-size: 11px; padding: 4px 10px; border-radius: 8px;',
            can_focus: true,
            reactive: true,
        });
        changeBtn.connect('clicked', () => {
            renderDropZoneView();
        });
        fileBadge.add_child(changeBtn);
        contentBin.add_child(fileBadge);

        // Section header
        let listHeader = new St.Label({
            text: 'Select nearby device:',
            style: 'font-size: 12px; color: rgba(255, 255, 255, 0.7); font-weight: 500; margin-bottom: 6px;',
        });
        contentBin.add_child(listHeader);

        // Container for peers
        let peersList = new St.BoxLayout({
            vertical: true,
            x_expand: true,
        });
        contentBin.add_child(peersList);

        let statusMsg = new St.Label({
            text: 'Searching for nearby devices...',
            style: 'font-size: 12px; color: rgba(255, 255, 255, 0.5); font-style: italic; margin-top: 8px;',
            x_align: Clutter.ActorAlign.CENTER,
        });
        peersList.add_child(statusMsg);

        // Fetch peers from companion daemon
        let fetchPeers = () => {
            try {
                let proc = Gio.Subprocess.new(
                    ['python3', '-c', "import urllib.request, json; print(urllib.request.urlopen('http://127.0.0.1:53317/api/drop/peers', timeout=2).read().decode())"],
                    Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
                );
                proc.communicate_utf8_async(null, null, (obj, res) => {
                    try {
                        let [, stdout] = obj.communicate_utf8_finish(res);
                        let data = JSON.parse(stdout || '{}');
                        let peers = data.peers || [];

                        peersList.destroy_all_children();

                        if (peers.length === 0) {
                            let emptyBox = new St.BoxLayout({
                                vertical: true,
                                style: 'padding: 16px 8px;',
                                x_align: Clutter.ActorAlign.CENTER,
                            });
                            let emptyLbl = new St.Label({
                                text: 'No nearby devices found.',
                                style: 'font-size: 12px; color: rgba(255, 255, 255, 0.6);',
                                x_align: Clutter.ActorAlign.CENTER,
                            });
                            emptyBox.add_child(emptyLbl);

                            let tipLbl = new St.Label({
                                text: 'Make sure MyNebula or PetalDrop is active on the nearby device.',
                                style: 'font-size: 11px; color: rgba(255, 255, 255, 0.4); margin-top: 4px;',
                                x_align: Clutter.ActorAlign.CENTER,
                            });
                            emptyBox.add_child(tipLbl);

                            let refreshBtn = new St.Button({
                                label: 'Refresh',
                                style_class: 'button',
                                style: 'margin-top: 10px; font-size: 11px; border-radius: 8px;',
                                x_align: Clutter.ActorAlign.CENTER,
                                can_focus: true,
                                reactive: true,
                            });
                            refreshBtn.connect('clicked', () => fetchPeers());
                            emptyBox.add_child(refreshBtn);

                            peersList.add_child(emptyBox);
                        } else {
                            peers.forEach(peer => {
                                let peerBtn = new St.Button({
                                    style_class: 'petaldrop-peer-btn',
                                    can_focus: true,
                                    reactive: true,
                                    x_expand: true,
                                });

                                let btnBox = new St.BoxLayout({
                                    vertical: false,
                                    x_expand: true,
                                    y_align: Clutter.ActorAlign.CENTER,
                                });

                                let iconName = peer.is_laptop ? 'computer-symbolic' : 'phone-symbolic';
                                let peerIcon = new St.Icon({
                                    icon_name: iconName,
                                    icon_size: 20,
                                    style: 'margin-right: 12px;',
                                });
                                btnBox.add_child(peerIcon);

                                let nameLbl = new St.Label({
                                    text: peer.name,
                                    y_align: Clutter.ActorAlign.CENTER,
                                    x_expand: true,
                                    style: 'font-weight: 500; font-size: 13px;',
                                });
                                btnBox.add_child(nameLbl);

                                let sendArrow = new St.Icon({
                                    icon_name: 'document-send-symbolic',
                                    icon_size: 16,
                                    style: 'color: #3584e4;',
                                });
                                btnBox.add_child(sendArrow);

                                peerBtn.set_child(btnBox);

                                peerBtn.connect('clicked', () => {
                                    sendToPeer(peer, filePath);
                                });

                                peersList.add_child(peerBtn);
                            });
                        }
                    } catch (e) {
                        peersList.destroy_all_children();
                        let errLbl = new St.Label({
                            text: 'Waiting for Nebula Companion daemon...',
                            style: 'font-size: 12px; color: rgba(255, 255, 255, 0.5);',
                            x_align: Clutter.ActorAlign.CENTER,
                        });
                        peersList.add_child(errLbl);
                    }
                });
            } catch (e) {}
        };

        // Function to execute the send
        let sendToPeer = (peer, fileToSend) => {
            peersList.destroy_all_children();

            let sendingBox = new St.BoxLayout({
                vertical: true,
                style: 'padding: 20px 8px;',
                x_align: Clutter.ActorAlign.CENTER,
            });

            let sendingLbl = new St.Label({
                text: `Sending to ${peer.name}...`,
                style: 'font-size: 14px; font-weight: 600; color: #ffffff;',
                x_align: Clutter.ActorAlign.CENTER,
            });
            sendingBox.add_child(sendingLbl);

            let subLbl = new St.Label({
                text: 'Transferring via PetalDrop...',
                style: 'font-size: 12px; color: rgba(255, 255, 255, 0.6); margin-top: 6px;',
                x_align: Clutter.ActorAlign.CENTER,
            });
            sendingBox.add_child(subLbl);

            peersList.add_child(sendingBox);

            try {
                let payload = JSON.stringify({
                    file_path: fileToSend,
                    target_ip: peer.ip,
                    target_port: peer.port || 53317
                });
                let script = `
import urllib.request, json
req = urllib.request.Request(
    'http://127.0.0.1:53317/api/drop/push',
    data=${JSON.stringify(payload)}.encode(),
    headers={'Content-Type': 'application/json'}
)
resp = urllib.request.urlopen(req, timeout=20)
print(resp.read().decode())
`;
                let proc = Gio.Subprocess.new(
                    ['python3', '-c', script],
                    Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
                );
                proc.communicate_utf8_async(null, null, (obj, res) => {
                    try {
                        let [, stdout] = obj.communicate_utf8_finish(res);
                        let result = JSON.parse(stdout || '{}');

                        sendingBox.destroy_all_children();

                        if (result.success) {
                            let okIcon = new St.Icon({
                                icon_name: 'emblem-ok-symbolic',
                                icon_size: 40,
                                style: 'color: #33d17a; margin-bottom: 8px;',
                                x_align: Clutter.ActorAlign.CENTER,
                            });
                            sendingBox.add_child(okIcon);

                            let okLbl = new St.Label({
                                text: `Successfully sent to ${peer.name}!`,
                                style: 'font-size: 14px; font-weight: 600; color: #ffffff;',
                                x_align: Clutter.ActorAlign.CENTER,
                            });
                            sendingBox.add_child(okLbl);

                            let againBtn = new St.Button({
                                label: 'Send another file',
                                style_class: 'button',
                                style: 'margin-top: 16px; border-radius: 9999px; padding: 6px 18px;',
                                x_align: Clutter.ActorAlign.CENTER,
                                can_focus: true,
                                reactive: true,
                            });
                            againBtn.connect('clicked', () => renderDropZoneView());
                            sendingBox.add_child(againBtn);
                        } else {
                            let errMsg = result.error || 'Connection error with device.';
                            let errIcon = new St.Icon({
                                icon_name: 'dialog-error-symbolic',
                                icon_size: 36,
                                style: 'color: #e01b24; margin-bottom: 8px;',
                                x_align: Clutter.ActorAlign.CENTER,
                            });
                            sendingBox.add_child(errIcon);

                            let errLbl = new St.Label({
                                text: `Transfer failed: ${errMsg}`,
                                style: 'font-size: 13px; color: #ff7b63;',
                                x_align: Clutter.ActorAlign.CENTER,
                            });
                            sendingBox.add_child(errLbl);

                            let retryBtn = new St.Button({
                                label: 'Retry',
                                style_class: 'button',
                                style: 'margin-top: 14px; border-radius: 9999px; padding: 6px 18px;',
                                x_align: Clutter.ActorAlign.CENTER,
                                can_focus: true,
                                reactive: true,
                            });
                            retryBtn.connect('clicked', () => renderPeersView(fileToSend));
                            sendingBox.add_child(retryBtn);
                        }
                    } catch (e) {
                        sendingBox.destroy_all_children();
                        let failLbl = new St.Label({
                            text: 'Error sending file.',
                            style: 'font-size: 13px; color: #ff7b63;',
                            x_align: Clutter.ActorAlign.CENTER,
                        });
                        sendingBox.add_child(failLbl);
                    }
                });
            } catch (e) {}
        };

        fetchPeers();
    };

    renderDropZoneView();

    _petalDropOverlay = overlay;
    Main.layoutManager.uiGroup.add_child(_petalDropOverlay);
    _petalDropOverlay.opacity = 0;
    _petalDropOverlay.ease({
        opacity: 255,
        duration: 250,
        mode: Clutter.AnimationMode.EASE_OUT_CUBIC,
    });
}

// ========================================================================
// 11. NebulaOS Setup Assistant Pre-Desktop Curtain & Fade-in Manager
// ========================================================================
let _setupCurtain = null;
let _setupCheckTimeoutId = null;
let _setupUnlocked = false;

function isLiveSession() {
    try {
        if (GLib.file_test('/cdrom/live/filesystem.squashfs', GLib.FileTest.EXISTS)) return true;
        if (GLib.file_test('/run/live', GLib.FileTest.EXISTS)) return true;
        if (GLib.get_user_name() === 'nebula') return true;
    } catch (e) {}
    return false;
}

function isWelcomePending() {
    try {
        if (isLiveSession()) return false;
        if (GLib.file_test('/run/nebula-desktop-unlocked', GLib.FileTest.EXISTS)) return false;
        let flagPath = GLib.get_home_dir() + '/.config/nebula/postinstall-wizard-completed';
        return !GLib.file_test(flagPath, GLib.FileTest.EXISTS);
    } catch (e) {}
    return false;
}

function shouldLockDesktopForSetup() {
    if (_setupUnlocked) return false;
    try {
        if (GLib.file_test('/run/nebula-desktop-unlocked', GLib.FileTest.EXISTS)) return false;
        let flagPath = GLib.get_home_dir() + '/.config/nebula/postinstall-wizard-completed';
        if (GLib.file_test(flagPath, GLib.FileTest.EXISTS)) return false;
    } catch (e) {}
    if (isLiveSession()) return true;
    if (isWelcomePending()) return true;
    return false;
}

function revealDesktopWithFadeIn() {
    try {
        log('[Nebula] Revealing GNOME desktop with smooth fade in…');

        // Restore Dash to Dock
        try {
            let dashActors = Main.uiGroup.get_children().filter(c => {
                let name = (c.get_name && c.get_name()) || '';
                let cl = (c.get_style_class_name && c.get_style_class_name()) || '';
                return name.includes('dashtodock') || cl.includes('dashtodock') || cl.includes('dock');
            });
            dashActors.forEach(a => {
                a.reactive = true;
                a.opacity = 255;
            });
        } catch (e) {}

        // Restore Main.panel with smooth fade-in
        if (Main.panel) {
            Main.panel.reactive = true;
            Main.panel.opacity = 255;
        }

        // Destroy black curtain immediately
        if (_setupCurtain) {
            try {
                _setupCurtain.destroy();
            } catch (e) {}
            _setupCurtain = null;
        }
    } catch (e) {
        log(`[Nebula] revealDesktopWithFadeIn error: ${e}`);
    }
}

function init() {
}

function enable() {
    // 0. Ensure ShowAppsIcon renders real colorful squircle
    if (Dash && Dash.ShowAppsIcon) {
        if (!_origShowAppsIconInit) {
            _origShowAppsIconInit = Dash.ShowAppsIcon.prototype._init;
        }
        Dash.ShowAppsIcon.prototype._init = function() {
            _origShowAppsIconInit.call(this);
            try {
                if (this.icon) {
                    if ('icon_name' in this.icon) {
                        this.icon.icon_name = 'view-app-grid';
                    } else if (typeof this.icon.set_icon_name === 'function') {
                        this.icon.set_icon_name('view-app-grid');
                    } else if ('gicon' in this.icon) {
                        this.icon.gicon = Gio.ThemedIcon.new('view-app-grid');
                    }
                    if (typeof this.icon.remove_style_class_name === 'function') {
                        this.icon.remove_style_class_name('show-apps-icon');
                    }
                }
            } catch (e) {}
        };
    }

    elevateDockActors();
    GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
        elevateDockActors();
        return GLib.SOURCE_REMOVE;
    });
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1200, () => {
        elevateDockActors();
        return GLib.SOURCE_REMOVE;
    });

    // ── Kiosk Lockdown ─────────────────────────────────────────────────────────
    // Hides the top panel and locks the GNOME overview during installer / welcome.
    // Dash-to-dock is NOT loaded at all (removed from gschema defaults), so no
    // dock actors ever exist during setup — nothing to hide there.
    // The panel.hide() + reactive=false approach is reliable because nothing
    // re-creates the panel. Polled every 200 ms as belt-and-suspenders.

    let isLiveSess = GLib.file_test('/run/live/medium', GLib.FileTest.EXISTS) ||
                     GLib.file_test('/cdrom/live/filesystem.squashfs', GLib.FileTest.EXISTS);

    let homeDir = GLib.get_home_dir ? GLib.get_home_dir() : '/root';
    let wizardDone = GLib.file_test(homeDir + '/.config/nebula/postinstall-wizard-completed',
                                    GLib.FileTest.EXISTS);
    let needsWelcome = !isLiveSess && !wizardDone;

    if (isLiveSess || needsWelcome) {
        // Lock overview immediately
        try {
            Main.overview.canToggle = function() { return false; };
            if (Main.overview.visible) Main.overview.hide();
        } catch (e) {}

        // Hide panel immediately
        let suppressPanel = () => {
            try {
                Main.panel.hide();
                Main.panel.opacity = 0;
                Main.panel.reactive = false;
            } catch (e) {}
        };
        suppressPanel();

        // Decide what "done" means
        let isDone = () => {
            if (isLiveSess) {
                return GLib.file_test('/run/nebula-desktop-unlocked', GLib.FileTest.EXISTS);
            }
            return !GLib.file_test('/run/nebula-welcome-active', GLib.FileTest.EXISTS) &&
                   GLib.file_test(homeDir + '/.config/nebula/postinstall-wizard-completed',
                                  GLib.FileTest.EXISTS);
        };

        // Poll every 200 ms
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 200, () => {
            if (isDone()) {
                try {
                    Main.panel.show();
                    Main.panel.opacity = 255;
                    Main.panel.reactive = true;
                    Main.overview.canToggle = function() { return true; };
                } catch (e) {}
                return GLib.SOURCE_REMOVE;
            }
            suppressPanel();
            return GLib.SOURCE_CONTINUE;
        });
    }



    // Search overlay — Ctrl+Shift+Space (via stage captured-event)
    try {
        if (!_spotlight) {
            _spotlight = new NebulaSpotlight();
        }
        _spotlightKeybindingId = global.stage.connect('captured-event', (actor, event) => {
            if (event.type() === Clutter.EventType.KEY_PRESS) {
                let sym = event.get_key_symbol();
                let state = event.get_state();
                let ctrlPressed = (state & Clutter.ModifierType.CONTROL_MASK) !== 0;
                let shiftPressed = (state & Clutter.ModifierType.SHIFT_MASK) !== 0;
                let isSpace = (sym === Clutter.KEY_space || sym === Clutter.KEY_KP_Space || sym === 32);

                if (ctrlPressed && shiftPressed && isSpace) {
                    if (_spotlight && _spotlight.visible) {
                        _spotlight.hide();
                    } else if (_spotlight) {
                        _spotlight.show();
                    }
                    return Clutter.EVENT_STOP;
                }
            }
            return Clutter.EVENT_PROPAGATE;
        });
    } catch (e) {
        log(`[Nebula] Search keybinding failed: ${e}`);
    }

    // 1. Notification Tray in Top-Right
    if (Main.messageTray && Main.messageTray._bannerBin) {
        _origBannerBinXAlign = Main.messageTray._bannerBin.x_align;
        _origBannerBinYAlign = Main.messageTray._bannerBin.y_align;
        _origBannerBinTranslationX = Main.messageTray._bannerBin.translation_x;

        Main.messageTray._bannerBin.set_x_align(Clutter.ActorAlign.END);
        Main.messageTray._bannerBin.set_y_align(Clutter.ActorAlign.START);
        Main.messageTray._bannerBin.translation_x = -28;
        Main.messageTray._bannerBin.translation_y = 16;
    }

    // 2. Notification Animations
    if (MessageTray && MessageTray.NotificationBanner) {
        if (!_origShowBanner) {
            _origShowBanner = MessageTray.NotificationBanner.prototype._show;
        }
        if (!_origHideBanner) {
            _origHideBanner = MessageTray.NotificationBanner.prototype._hide;
        }

        MessageTray.NotificationBanner.prototype._show = function() {
            this.translation_x = 90;
            this.translation_y = -30;
            this.opacity = 0;
            this.set_pivot_point(0.5, 0.5);
            this.scale_x = 0.85;
            this.scale_y = 0.85;

            this.ease({
                opacity: 255,
                duration: 220,
                mode: Clutter.AnimationMode.EASE_OUT_QUAD
            });

            this.ease({
                translation_x: 0,
                translation_y: 0,
                scale_x: 1.0,
                scale_y: 1.0,
                duration: 440,
                mode: Clutter.AnimationMode.EASE_OUT_BACK
            });
        };

        if (!_origUpdateIcon) {
            _origUpdateIcon = MessageTray.NotificationBanner.prototype._updateIcon;
        }

        MessageTray.NotificationBanner.prototype._updateIcon = function() {
            if (!this._iconBin) return;
            this._iconBin.child = null;
            let icon = null;

            let app = this.source ? (this.source.app || null) : null;
            if (!app && this.source && this.source.id) {
                try {
                    let appSys = Shell.AppSystem.get_default();
                    app = appSys.lookup_app(this.source.id) ||
                          appSys.lookup_app(this.source.id + '.desktop');
                } catch (e) {}
            }

            if (app) {
                try {
                    icon = app.create_icon_texture(54);
                } catch (e) {}
            }

            if (!icon && this.notification && this.notification.iconName) {
                let iname = this.notification.iconName;
                let isSystemOrSymbolic = iname.includes('symbolic') ||
                                         iname.startsWith('battery') ||
                                         iname.startsWith('network') ||
                                         iname.startsWith('dialog') ||
                                         iname.startsWith('system') ||
                                         iname.startsWith('preferences') ||
                                         iname.startsWith('drive') ||
                                         iname.startsWith('audio') ||
                                         iname.startsWith('media') ||
                                         iname.startsWith('notification');
                if (!isSystemOrSymbolic) {
                    try {
                        icon = new St.Icon({
                            icon_name: iname,
                            icon_size: 54,
                            style_class: 'notification-icon'
                        });
                    } catch (e) {}
                }
            }

            if (!icon) {
                try {
                    let appSys = Shell.AppSystem.get_default();
                    let settingsApp = appSys.lookup_app('org.gnome.Settings.desktop') ||
                                      appSys.lookup_app('gnome-control-center.desktop');
                    if (settingsApp) {
                        icon = settingsApp.create_icon_texture(54);
                    }
                } catch (e) {}

                if (!icon) {
                    try {
                        icon = new St.Icon({
                            icon_name: 'org.gnome.Settings',
                            icon_size: 54,
                            style_class: 'notification-icon'
                        });
                    } catch (e) {}
                }
            }

            if (icon) {
                this._iconBin.child = icon;
            }
        };
    }

    // 3. Dynamic Topbar
    if (global.workspace_manager) {
        _switchWorkspaceId = global.workspace_manager.connect('active-workspace-changed', () => {
            updatePanelOpacity();
        });
    }

    if (global.display) {
        let winCreatedTracker = global.display.connect('window-created', (display, metaWindow) => {
            watchWindow(metaWindow);
            updatePanelOpacity();
        });
        _panelWindowSignals.push([global.display, winCreatedTracker]);

        try {
            for (let w of global.display.list_all_windows()) {
                watchWindow(w);
            }
        } catch (e) {}
    }

    updatePanelOpacity();

    // 4. Launchpad / App Grid & Overview Hooks
    if (Main.overview) {
        _overviewShowingId = Main.overview.connect('showing', () => {
            updatePanelOpacity();

            try {
                const controls = Main.overview._overview ? Main.overview._overview._controls : null;
                const appDisplay = controls ? (controls._appDisplay || controls.appDisplay) : null;
                const targetActor = appDisplay || controls;

                if (targetActor) {
                    targetActor.translation_y = 140;
                    targetActor.opacity = 20;
                    targetActor.ease({
                        translation_y: 0,
                        opacity: 255,
                        duration: 380,
                        mode: Clutter.AnimationMode.EASE_OUT_CUBIC
                    });
                }
            } catch (e) {}
        });

        _overviewHidingId = Main.overview.connect('hiding', () => {
            updatePanelOpacity();
        });
    }

    // 5. App Window Opening Animation
    if (global.display) {
        _windowCreatedId = global.display.connect('window-created', (display, metaWindow) => {
            if (!metaWindow || metaWindow.get_window_type() !== Meta.WindowType.NORMAL) {
                return;
            }

            GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                try {
                    const actor = metaWindow.get_compositor_private();
                    if (!actor) return GLib.SOURCE_REMOVE;

                    actor.set_pivot_point(0.15, 0.15);
                    actor.scale_x = 0.4;
                    actor.scale_y = 0.4;
                    actor.opacity = 40;

                    actor.ease({
                        scale_x: 1.0,
                        scale_y: 1.0,
                        opacity: 255,
                        duration: 340,
                        mode: Clutter.AnimationMode.EASE_OUT_CUBIC
                    });
                } catch (e) {}
                return GLib.SOURCE_REMOVE;
            });
        });
    }

    // 6. Smooth Fade-Out to Black on Shutdown / Reboot
    function triggerScreenFadeOut(callback) {
        if (!Main.uiGroup) {
            if (callback) callback();
            return;
        }
        let blackCover = new St.Widget({
            style: 'background-color: #000000;',
            reactive: true,
            opacity: 0,
            x: 0,
            y: 0,
            width: global.screen_width,
            height: global.screen_height
        });
        Main.uiGroup.add_child(blackCover);
        blackCover.ease({
            opacity: 255,
            duration: 650,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => {
                if (callback) callback();
            }
        });
    }

    try {
        const LoginManager = imports.misc.loginManager ? imports.misc.loginManager.getLoginManager() : null;
        if (LoginManager) {
            let origPowerOff = LoginManager.powerOff.bind(LoginManager);
            let origReboot = LoginManager.reboot.bind(LoginManager);
            LoginManager.powerOff = function() {
                triggerScreenFadeOut(() => origPowerOff());
            };
            LoginManager.reboot = function() {
                triggerScreenFadeOut(() => origReboot());
            };
        }
    } catch (e) {}

    try {
        const EndSession = imports.ui.endSessionDialog;
        if (EndSession && EndSession.EndSessionDialog) {
            let origConfirm = EndSession.EndSessionDialog.prototype._confirm;
            EndSession.EndSessionDialog.prototype._confirm = function(signal) {
                triggerScreenFadeOut(() => {
                    origConfirm.call(this, signal);
                });
            };
        }
    } catch (e) {}

    // Top bar dateMenu in lockscreen/gdm modes
    try {
        if (Main.sessionMode) {
            _sessionUpdatedId = Main.sessionMode.connect('updated', updateDateMenuVisibility);
            if (Main.sessionMode._modes) {
                if (Main.sessionMode._modes['unlock-dialog'] && Main.sessionMode._modes['unlock-dialog'].panel) {
                    Main.sessionMode._modes['unlock-dialog'].panel.center = [];
                }
                if (Main.sessionMode._modes['gdm'] && Main.sessionMode._modes['gdm'].panel) {
                    Main.sessionMode._modes['gdm'].panel.center = [];
                }
            }
            updateDateMenuVisibility();
        }
    } catch (e) {}

    // UserWidgetLabel Hook (Centering real name and username)
    if (UserWidget && UserWidget.UserWidgetLabel) {
        if (!_origUserWidgetLabelInit) {
            _origUserWidgetLabelInit = UserWidget.UserWidgetLabel.prototype._init;
        }
        UserWidget.UserWidgetLabel.prototype._init = function(user) {
            _origUserWidgetLabelInit.call(this, user);
            try {
                this.x_align = Clutter.ActorAlign.CENTER;
                if (this._realNameLabel) {
                    this._realNameLabel.x_align = Clutter.ActorAlign.CENTER;
                    if (this._realNameLabel.clutter_text) {
                        this._realNameLabel.clutter_text.set_line_alignment(Pango.Alignment.CENTER);
                        this._realNameLabel.clutter_text.set_ellipsize(Pango.EllipsizeMode.NONE);
                    }
                }
                if (this._userNameLabel) {
                    this._userNameLabel.x_align = Clutter.ActorAlign.CENTER;
                    if (this._userNameLabel.clutter_text) {
                        this._userNameLabel.clutter_text.set_line_alignment(Pango.Alignment.CENTER);
                        this._userNameLabel.clutter_text.set_ellipsize(Pango.EllipsizeMode.NONE);
                    }
                }
            } catch (e) {}
        };
    }

    // 7. Standard GNOME GDM and Lockscreen are preserved natively with blurred wallpaper

    // 10. PetalDrop Quick Settings Toggle in Control Panel
    try {
        if (QuickSettings && QuickSettings.QuickToggle && Main.panel && Main.panel.statusArea && Main.panel.statusArea.quickSettings) {
            let PetalDropToggle = GObject.registerClass(
            class PetalDropToggle extends QuickSettings.QuickToggle {
                _init() {
                    super._init({
                        title: 'PetalDrop',
                        label: 'PetalDrop',
                        iconName: 'document-send-symbolic',
                        toggleMode: false,
                    });
                }
            });

            _petalDropToggle = new PetalDropToggle();
            _petalDropToggle.connect('clicked', () => {
                try {
                    Main.panel.statusArea.quickSettings.menu.close();
                } catch (e) {}
                togglePetalDropOverlay();
            });

            let qs = Main.panel.statusArea.quickSettings;
            if (qs.addItem) {
                qs.addItem(_petalDropToggle, 2);
            } else if (qs.menu && qs.menu.addItem) {
                qs.menu.addItem(_petalDropToggle, 2);
            } else if (qs._grid) {
                qs._grid.add_child(_petalDropToggle);
            }
        }
    } catch (e) {
        log(`[Nebula] PetalDrop quick toggle init error: ${e}`);
    }

    // App Launch Lockdown: prevent starting arbitrary apps before setup / welcome wizard completes
    try {
        if (Shell && Shell.App) {
            let _origAppActivate = Shell.App.prototype.activate;
            let _origAppActivateFull = Shell.App.prototype.activate_full;
            Shell.App.prototype.activate = function(...args) {
                if (shouldLockDesktopForSetup()) {
                    let id = (this.get_id && this.get_id()) || '';
                    if (!id.includes('installer') && !id.includes('welcome') && !id.includes('setup') && !id.includes('recovery')) {
                        log(`[Nebula] Blocked app launch before setup completion: ${id}`);
                        return;
                    }
                }
                return _origAppActivate.apply(this, args);
            };
            Shell.App.prototype.activate_full = function(...args) {
                if (shouldLockDesktopForSetup()) {
                    let id = (this.get_id && this.get_id()) || '';
                    if (!id.includes('installer') && !id.includes('welcome') && !id.includes('setup') && !id.includes('recovery')) {
                        log(`[Nebula] Blocked app launch before setup completion: ${id}`);
                        return;
                    }
                }
                return _origAppActivateFull.apply(this, args);
            };
        }
    } catch (e) {
        log(`[Nebula] App lockdown hook error: ${e}`);
    }

    // Position PetalDrop native window top-right, keep above, sticky
    if (global.display && !_petalDropWinSignal) {
        _petalDropWinSignal = global.display.connect('window-created', (display, metaWindow) => {
            try {
                if (!metaWindow) return;
                let wmClass = (metaWindow.get_wm_class && metaWindow.get_wm_class()) || '';
                let title = (metaWindow.get_title && metaWindow.get_title()) || '';
                if (wmClass.includes('petaldrop') || title === 'PetalDrop') {
                    metaWindow.make_above();
                    metaWindow.stick();
                    let monitor = Main.layoutManager.primaryMonitor;
                    if (monitor) {
                        let targetX = monitor.x + monitor.width - 456;
                        let targetY = monitor.y + (Main.panel ? Main.panel.height : 32) + 12;
                        GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                            try {
                                metaWindow.move_frame(true, targetX, targetY);
                            } catch (e) {}
                            return GLib.SOURCE_REMOVE;
                        });
                    }
                }
            } catch (e) {}
        });
    }

    // 11. Pre-Desktop Setup Assistant: hide dock and overview until setup completion
    if (shouldLockDesktopForSetup()) {
        try {
            log('[Nebula] Setup mode detected: hiding dock and ensuring clean desktop start…');

            // Hide Dash to Dock until setup completion
            let hideDock = () => {
                try {
                    let dashActors = Main.uiGroup.get_children().filter(c => {
                        let name = (c.get_name && c.get_name()) || '';
                        let cl = (c.get_style_class_name && c.get_style_class_name()) || '';
                        return name.includes('dashtodock') || cl.includes('dashtodock') || cl.includes('dock');
                    });
                    dashActors.forEach(a => { a.opacity = 0; a.reactive = false; });
                } catch (e) {}
            };
            hideDock();
            [200, 500, 1000, 2000].forEach(delay => {
                GLib.timeout_add(GLib.PRIORITY_DEFAULT, delay, () => {
                    if (!_setupUnlocked) hideDock();
                    return GLib.SOURCE_REMOVE;
                });
            });

            // Dismiss overview so we start directly on desktop
            try {
                if (Main.overview && Main.overview.visible) Main.overview.hide();
            } catch (e) {}

            // Poll for setup unlock / completion
            _setupCheckTimeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 150, () => {
                if (_setupUnlocked) return GLib.SOURCE_REMOVE;
                let unlocked = false;
                try {
                    if (GLib.file_test('/run/nebula-desktop-unlocked', GLib.FileTest.EXISTS)) {
                        unlocked = true;
                    } else if (!isLiveSession() && !isWelcomePending()) {
                        unlocked = true;
                    }
                } catch (e) {}

                if (unlocked) {
                    _setupUnlocked = true;
                    revealDesktopWithFadeIn();
                    return GLib.SOURCE_REMOVE;
                }
                return GLib.SOURCE_CONTINUE;
            });
        } catch (e) {
            log(`[Nebula] Setup mode handler error: ${e}`);
        }
    } else {
        // Not in setup mode — ensure panel and dock are fully visible
        if (Main.panel) {
            Main.panel.opacity = 255;
            Main.panel.reactive = true;
        }
    }
}

function disable() {
    if (_setupCheckTimeoutId) {
        try { GLib.source_remove(_setupCheckTimeoutId); } catch (e) {}
        _setupCheckTimeoutId = null;
    }
    if (_petalDropWinSignal && global.display) {
        try { global.display.disconnect(_petalDropWinSignal); } catch (e) {}
        _petalDropWinSignal = null;
    }
    if (_petalDropIndicator) {
        try { _petalDropIndicator.destroy(); } catch (e) {}
        _petalDropIndicator = null;
    }
    if (_petalDropToggle) {
        try { _petalDropToggle.destroy(); } catch (e) {}
        _petalDropToggle = null;
    }
    if (_petalDropOverlay) {
        try { _petalDropOverlay.destroy(); } catch (e) {}
        _petalDropOverlay = null;
    }
    // Restore tray positioning
    if (Main.messageTray && Main.messageTray._bannerBin) {
        if (_origBannerBinXAlign !== null) Main.messageTray._bannerBin.set_x_align(_origBannerBinXAlign);
        if (_origBannerBinYAlign !== null) Main.messageTray._bannerBin.set_y_align(_origBannerBinYAlign);
        Main.messageTray._bannerBin.translation_x = _origBannerBinTranslationX;
        Main.messageTray._bannerBin.translation_y = 0;
    }

    // Restore banner methods
    if (MessageTray && MessageTray.NotificationBanner) {
        if (_origShowBanner) MessageTray.NotificationBanner.prototype._show = _origShowBanner;
        if (_origHideBanner) MessageTray.NotificationBanner.prototype._hide = _origHideBanner;
        if (_origUpdateIcon) MessageTray.NotificationBanner.prototype._updateIcon = _origUpdateIcon;
    }

    // Destroy Spotlight
    if (_spotlightKeybindingId && global.stage) {
        try { global.stage.disconnect(_spotlightKeybindingId); } catch (e) {}
        _spotlightKeybindingId = null;
    }
    if (_spotlight) {
        try { _spotlight.destroy(); } catch (e) {}
        _spotlight = null;
    }

    // Restore Topbar
    if (Main.panel) {
        Main.panel.remove_style_class_name('panel-opaque');
    }
    if (_switchWorkspaceId && global.workspace_manager) {
        global.workspace_manager.disconnect(_switchWorkspaceId);
        _switchWorkspaceId = null;
    }
    for (let item of _panelWindowSignals) {
        try {
            if (item.length === 2) {
                item[0].disconnect(item[1]);
            } else if (item.length === 3) {
                item[0].disconnect(item[1]);
                item[0].disconnect(item[2]);
            }
        } catch (e) {}
    }
    _panelWindowSignals = [];

    if (_overviewShowingId && Main.overview) {
        Main.overview.disconnect(_overviewShowingId);
        _overviewShowingId = null;
    }
    if (_overviewHidingId && Main.overview) {
        Main.overview.disconnect(_overviewHidingId);
        _overviewHidingId = null;
    }

    if (_windowCreatedId && global.display) {
        global.display.disconnect(_windowCreatedId);
        _windowCreatedId = null;
    }

    if (Dash && Dash.ShowAppsIcon && _origShowAppsIconInit) {
        Dash.ShowAppsIcon.prototype._init = _origShowAppsIconInit;
        _origShowAppsIconInit = null;
    }

    if (_sessionUpdatedId && Main.sessionMode) {
        Main.sessionMode.disconnect(_sessionUpdatedId);
        _sessionUpdatedId = null;
    }
    if (Main.panel && Main.panel.statusArea && Main.panel.statusArea.dateMenu) {
        Main.panel.statusArea.dateMenu.visible = true;
    }

    if (UserWidget && UserWidget.UserWidgetLabel && _origUserWidgetLabelInit) {
        UserWidget.UserWidgetLabel.prototype._init = _origUserWidgetLabelInit;
        _origUserWidgetLabelInit = null;
    }
}
