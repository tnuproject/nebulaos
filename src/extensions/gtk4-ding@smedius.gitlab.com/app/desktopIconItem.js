
/* DING: Desktop Icons New Generation for GNOME Shell
 *
 * Gtk4 Port Copyright (C) 2022 Sundeep Mediratta (smedius@gmail.com)
 * Copyright (C) 2021 Sundeep Mediratta (smedius@gmail.com)
 * Copyright (C) 2019 Sergio Costas (rastersoft@gmail.com)
 * Based on code original (C) Carlos Soriano
 * SwitcherooControl code based on code original from Marsch84
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

const { Gtk, Gdk, Gio, GLib, Pango, GdkPixbuf } = imports.gi;
const DesktopIconsUtil = imports.utils.desktopIconsUtil;
const FileUtils = imports.utils.fileUtils;

const Prefs = imports.app.preferences;
const Enums = imports.app.enums;

const Signals = imports.signals;
const Gettext = imports.gettext.domain('gtk4-ding');

const _ = Gettext.gettext;

const PIXBUF_CONTENT_TYPES = new Set();
GdkPixbuf.Pixbuf.get_formats().forEach(f => PIXBUF_CONTENT_TYPES.add(...f.get_mime_types()));

var desktopIconItem = class desktopIconItem {
    constructor(desktopManager, fileExtra) {
        this._desktopManager = desktopManager;
        this._fileExtra = fileExtra;
        this._queryFileInfoCancellable = null;
        this._grid = null;
        this._lastClickTime = 0;
        this._lastClickButton = 0;
        this._clickCount = 0;
        this._isSelected = false;
        this._isSpecial = false;
        this._primaryButtonPressed = false;
        this._savedCoordinates = null;
        this._dropCoordinates = null;
        this._destroyed = false;
        this.thumbnailFile = null;
    }

    /** *********************
     * Destroyers *
     ***********************/

    removeFromGrid(opts = { callOnDestroy: false }) {
        if (this._grid) {
            this._grid.removeItem(this);
            this._grid = null;
        }
        if (opts.callOnDestroy)
            this.onDestroy();
    }

    _destroy() {
        /* Regular file data */
        if (this._queryFileInfoCancellable)
            this._queryFileInfoCancellable.cancel();


        /* Icons update */
        if (this._updateIconCancellable)
            this._updateIconCancellable.cancel();

        /* Container */
        if (this._containerId) {
            this.container.disconnect(this._containerId);
            this._containerId = 0;
        }
        /* DragItem */
        if (this.dragIconSignal)
            this.dragIcon.disconnect(this.dragIconSignal);
    }

    onDestroy() {
        this._destroy();
        this._destroyed = true;
    }

    /** *********************
     * Creators *
     ***********************/

    _createIconActor() {
        this.container = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, halign: Gtk.Align.CENTER });
        this._containerId = this.container.connect('destroy', () => this.onDestroy());

        this._icon = new Gtk.Picture();
        this._icon.set_can_shrink(false);
        this._icon.set_keep_aspect_ratio(true);
        this._icon.set_halign(Gtk.Align.CENTER);
        this._iconContainer = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL });
        this._iconContainer.set_hexpand(false);
        this._iconContainer.set_halign(Gtk.Align.CENTER);
        this._iconContainer.set_baseline_position(Gtk.BaselinePosition.CENTER);
        this._iconContainer.append(this._icon);

        this._label = new Gtk.Label();
        this._labelContainer = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, halign: Gtk.Align.CENTER });
        let labelStyleContext = this._label.get_style_context();
        if (this._desktopManager.darkText)
            labelStyleContext.add_class('file-label-dark');
        else
            labelStyleContext.add_class('file-label');

        this._label.set_ellipsize(Pango.EllipsizeMode.END);
        this._label.set_wrap(true);
        this._label.set_wrap_mode(Pango.WrapMode.WORD_CHAR);
        this._label.set_yalign(0.0);
        this._label.set_justify(Gtk.Justification.CENTER);
        this._label.set_lines(2);
        this._labelContainer.append(this._label);

        this.container.append(this._iconContainer);
        this.container.append(this._labelContainer);

        this._styleContext = this._iconContainer.get_style_context();
        this._labelStyleContext = this._labelContainer.get_style_context();
        this._styleContext.add_class('file-item');
        this._labelStyleContext.add_class('file-item');

        this.iconRectangle = new Gdk.Rectangle();
        this.labelRectangle = new Gdk.Rectangle();

        this._iconEventController = Gtk.EventControllerMotion.new();
        this._iconEventController.set_propagation_phase(Gtk.PropagationPhase.TARGET);
        this._iconEventController.connect('enter', () => this._onEnter());
        this._iconEventController.connect('leave', () => this._onLeave());
        this._iconContainer.add_controller(this._iconEventController);

        this._labelEventController = Gtk.EventControllerMotion.new();
        this._labelEventController.set_propagation_phase(Gtk.PropagationPhase.TARGET);
        this._labelEventController.connect('enter', () => this._onEnter());
        this._labelEventController.connect('leave', () => this._onLeave());
        this._labelContainer.add_controller(this._labelEventController);

        this.dragIcon = Gtk.WidgetPaintable.new(this.container);
        this.dragIconSignal = this.dragIcon.connect('invalidate-size', () => {
            this._doIconSizeAllocated();
        });

        this.container.show();
    }

    _doIconSizeAllocated() {
        // If icons are hidden during stacking, they are not assigned a grid //
        if (!this._grid)
            return;

        this._calculateIconRectangle();
        this._calculateLabelRectangle();
        this.iconPlacedPromiseResolve(true);
    }

    iconPlaced = new Promise(resolve => {
        this.iconPlacedPromiseResolve = resolve;
    });

    _calculateIconRectangle() {
        this.iconwidth = this._iconContainer.get_allocated_width();
        this.iconheight = this._iconContainer.get_allocated_height();
        let [x, y] = this._grid.coordinatesLocalToGlobal(0, 0, this._iconContainer);
        this.iconRectangle.x = x;
        this.iconRectangle.y = y;
        this.iconRectangle.width = this.iconwidth;
        this.iconRectangle.height = this.iconheight;
    }

    _calculateLabelRectangle() {
        this.labelwidth = this._labelContainer.get_allocated_width();
        this.labelheight = this._labelContainer.get_allocated_height();
        let [x, y] = this._grid.coordinatesLocalToGlobal(0, 0, this._labelContainer);
        this.labelRectangle.x = x;
        this.labelRectangle.y = y;
        this.labelRectangle.width = this.labelwidth;
        this.labelRectangle.height = this.labelheight;
    }

    setCoordinates(x, y, width, height, margin, grid) {
        this._x1 = x;
        this._y1 = y;
        this.width = width;
        this.height = height;
        this._grid = grid;
        this.container.set_size_request(width, height);
        this._label.margin_start = margin;
        this._label.margin_end = margin;
        this._label.margin_bottom = margin;
        this._iconContainer.margin_top = margin;
        this._calculateIconRectangle();
        this._calculateLabelRectangle();
    }

    getCoordinates() {
        this._x2 = this._x1 + this.container.get_allocated_width() - 1;
        this._y2 = this._y1 + this.container.get_allocated_height() - 1;
        return [this._x1, this._y1, this._x2, this._y2, this._grid];
    }

    _setLabelName(text) {
        var nextChar;
        this._currentFileName = text;
        this._iconContainer.set_tooltip_text(text);
        let lastCutPos = -1;
        let newText = '';
        for (let pos = 0; pos < text.length; pos++) {
            let character = text[pos];
            newText += character;
            if (pos < (text.length - 1))
                nextChar = text[pos + 1];
            else
                nextChar = '';

            if (character === ' ')
                lastCutPos = pos;

            if (['.', ',', '-', '_', '@', ':'].includes(character)) {
                /* if the next character is already an space or this is the last
                 * character, the string will be naturally cut here, so we do
                 * nothing.
                 */
                if ((nextChar === ' ') || (nextChar === ''))
                    continue;

                /* if there is a cut element in the last four previous characters,
                 * do not add a new cut element.
                 */
                if ((lastCutPos > -1) && ((pos - lastCutPos) < 4))
                    continue;

                newText += '\u200B';
            }
        }
        this._label.label = newText;
    }

    /** *********************
     * Button Clicks *
     ***********************/

    _updateClickState(button, eventtime) {
        let settings = Gtk.Settings.get_default();

        if ((button === this._lastClickButton) &&
            ((eventtime - this._lastClickTime) < settings.gtk_double_click_time))
            this._clickCount++;
        else
            this._clickCount = 1;

        this._lastClickTime = eventtime;
        this._lastClickButton = button;
    }

    getClickCount() {
        return this._clickCount;
    }

    _onPressButton(actor, X, Y, x, y, shiftPressed, controlPressed) {
        let button = actor.get_current_button();
        let eventtime = actor.get_current_event_time();
        this._updateClickState(button, eventtime);
        this._buttonPressInitialX = x - this._x1;
        this._buttonPressInitialY = y - this._y1;
        this._desktopManager.activeFileItem = this._desktopManager.fileItemMenu.activeFileItem = this;
        if (button === 3)
            this._doButtonThreePressed(button, X, Y, x, y, shiftPressed, controlPressed);
        else if (button === 1)
            this._doButtonOnePressed(button, X, Y, x, y, shiftPressed, controlPressed);
    }

    _onReleaseButton(actor, X, Y, x, y, shiftPressed, controlPressed) {
        let button = actor.get_current_button();
        if (button === 1)
            this._doButtonOneReleased(button, X, Y, x, y, shiftPressed, controlPressed);
    }

    _doButtonThreePressed(button, X, Y, x, y, shiftPressed, controlPressed) {
        if (!this._isSelected)
            this._desktopManager.selected(this, Enums.Selection.RIGHT_BUTTON);

        this._desktopManager.fileItemMenu.showMenu(this, button, X, Y, x, y, shiftPressed, controlPressed);
    }

    _doButtonOnePressed(button, X, Y, x, y, shiftPressed, controlPressed) {
        if (this.getClickCount() === 1) {
            this._primaryButtonPressed = true;
            if (shiftPressed || controlPressed)
                this._desktopManager.selected(this, Enums.Selection.WITH_SHIFT);
            else
                this._desktopManager.selected(this, Enums.Selection.ALONE);
        }
    }

    _doButtonOneReleased(button, X, Y, x, y, shiftPressed, controlPressed) {
    }

    /** *********************
     * Drag and Drop *
     ***********************/

    _onEnter() {
        if (!this._styleContext.has_class('file-item-hover')) {
            this._styleContext.add_class('file-item-hover');
            this._labelStyleContext.add_class('file-item-hover');
        }
        if (Prefs.CLICK_POLICY_SINGLE) {
            let window = this._grid._window;
            if (window)
                window.set_cursor(Gdk.Cursor.new_from_name('hand', null));
        }
        return false;
    }

    _onLeave() {
        this._primaryButtonPressed = false;
        if (this._styleContext.has_class('file-item-hover')) {
            this._styleContext.remove_class('file-item-hover');
            this._labelStyleContext.remove_class('file-item-hover');
        }
        if (Prefs.CLICK_POLICY_SINGLE) {
            let window = this._grid._window;
            if (window)
                window.set_cursor(Gdk.Cursor.new_from_name('default', null));
        }
        return false;
    }

    _hasToRouteDragToGrid() {
        if (this._grid)
            return true;
    }

    _updateDragStatus(context, time) {
        if (DesktopIconsUtil.getModifiersInDnD(context, Gdk.ModifierType.CONTROL_MASK))
            Gdk.drag_status(context, Gdk.DragAction.COPY, time);
        else
            Gdk.drag_status(context, Gdk.DragAction.MOVE, time);
    }

    highLightDropTarget() {
        if (this._hasToRouteDragToGrid()) {
            this._grid.receiveMotion(this._x1, this._y1, true);
            return;
        }
        if (!this._styleContext.has_class('desktop-icons-selected')) {
            this._styleContext.add_class('desktop-icons-selected');
            this._labelStyleContext.add_class('desktop-icons-selected');
        }
        this._grid.highLightGridAt(this._x1, this._y1);
    }

    unHighLightDropTarget() {
        if (this._hasToRouteDragToGrid()) {
            this._grid.receiveLeave();
            return;
        }
        if (!this._isSelected && this._styleContext.has_class('desktop-icons-selected')) {
            this._styleContext.remove_class('desktop-icons-selected');
            this._labelStyleContext.remove_class('desktop-icons-selected');
        }
        this._grid.unHighLightGrids();
    }

    setSelected() {
        this._isSelected = true;
        this._setSelectedStatus();
    }

    unsetSelected() {
        this._isSelected = false;
        this._setSelectedStatus();
    }

    toggleSelected() {
        this._isSelected = !this._isSelected;
        this._setSelectedStatus();
    }

    _setSelectedStatus() {
        if (this._isSelected && !this._styleContext.has_class('desktop-icons-selected')) {
            this._styleContext.add_class('desktop-icons-selected');
            this._labelStyleContext.add_class('desktop-icons-selected');
        }
        if (!this._isSelected && this._styleContext.has_class('desktop-icons-selected')) {
            this._styleContext.remove_class('desktop-icons-selected');
            this._labelStyleContext.remove_class('desktop-icons-selected');
        }
    }

    _calculateOffset(X, Y) {
        return [Math.round(X - this._x1), Math.round(Y - this._y1)];
    }

    receiveDrop(x, y, selection, info) {
    }

    dropCapable() {
        return false;
    }

    /** *********************
     * Icon Rendering *
     ***********************/

    async updateIcon() {
        await this._updateIcon().catch(e => {
            if (!e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED)) {
                logError(e, `Exception while updating ${this._getVisibleName
                    ? this._getVisibleName() : 'an icon'}: ${e.message}`);
            }
        });
    }

    async _updateIcon(cancellable) {
        if ((cancellable && cancellable.is_cancelled()) || this._destroyed) {
            throw new GLib.Error(Gio.IOErrorEnum,
                Gio.IOErrorEnum.CANCELLED,
                'Operation was cancelled');
        } else if (!cancellable) {
            cancellable = new Gio.Cancellable();
        }

        if (this._updateIconCancellable)
            this._updateIconCancellable.cancel();

        this._updateIconCancellable = cancellable;

        try {
            let customIcon = this._fileInfo.get_attribute_as_string('metadata::custom-icon');
            if (customIcon && (customIcon !== '')) {
                let customIconFile = Gio.File.new_for_uri(customIcon);
                if (await this._loadImageAsIcon(customIconFile, cancellable))
                    return;
            }
            if (this.thumbnailFile && (this.thumbnailFile !== '')) {
                let customIconFile = Gio.File.new_for_path(this.thumbnailFile);
                if (await FileUtils.queryExists(customIconFile)) {
                    let loadedImage = await this._loadImageAsIcon(customIconFile, cancellable);
                    if (loadedImage | this._destroyed)
                        return;
                }
            }
        } catch (error) {
            if (error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                throw error;

            logError(error, `Error while updating icon: ${error.message}`);
        }

        if (this._fileExtra === Enums.FileType.USER_DIRECTORY_TRASH) {
            let pixbuf = this._createEmblemedIcon(this._fileInfo.get_icon(), null);
            if (cancellable.is_cancelled())
                return;
            this._icon.set_paintable(pixbuf);
            return;
        }

        let iconSet = false;

        if ((Prefs.nautilusSettings.get_string('show-image-thumbnails') !== 'never') &&
            this._desktopManager.thumbnailLoader.canThumbnail(this)) {
            try {
                const thumbnail = await this._desktopManager.thumbnailLoader.getThumbnail(
                    this, cancellable);
                if (thumbnail !== null) {
                    let thumbnailFile = Gio.File.new_for_path(thumbnail);
                    iconSet = await this._loadImageAsIcon(thumbnailFile, cancellable);
                }
            } catch (e) {
                if (e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                    throw e;

                logError(e, `Error while generating thumbnail: ${e.message}`);
            }
        }

        if (!iconSet &&
            Prefs.nautilusSettings.get_string('show-image-thumbnails') !== 'never' &&
            this.fileSize < 5242880 &&
            PIXBUF_CONTENT_TYPES.has(this._fileInfo.get_content_type())) {
            try {
                iconSet = await this._loadImageAsIcon(
                    Gio.File.new_for_uri(this.uri), cancellable);
            } catch (e) {
                if (e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                    throw e;

                logError(e, `Error while generating icon image: ${e.message}`);
            }
        }

        if (!iconSet) {
            let iconPaintable;
            if (this._isBrokenSymlink)
                iconPaintable = this._createEmblemedIcon(null, 'text-x-generic');
            else if (this._desktopFile && this._desktopFile.has_key('Icon'))
                iconPaintable = this._createEmblemedIcon(null, this._desktopFile.get_string('Icon'));
            else
                iconPaintable = this._createEmblemedIcon(this._getDefaultIcon(), null);

            if (cancellable.is_cancelled())
                return;
            this._icon.set_paintable(iconPaintable);
        }

        if (cancellable === this._updateIconCancellable)
            this._updateIconCancellable = null;
    }

    _getDefaultIcon() {
        if (this._fileExtra === Enums.FileType.EXTERNAL_DRIVE)
            return this._custom.get_icon();

        return this._fileInfo.get_icon();
    }

    async _loadImageAsIcon(imageFile, cancellable) {
        try {
            const [thumbnailData] = await imageFile.load_bytes_async(cancellable);
            const iconTexture = Gdk.Texture.new_from_bytes(thumbnailData);
            let width = Prefs.get_desired_width() - 8;
            let height = Prefs.get_icon_size() - 8;
            const aspectRatio = iconTexture.width / iconTexture.height;
            if ((width / height) > aspectRatio)
                width = height * aspectRatio;
            else
                height = width / aspectRatio;
            let iconPaintableSnapshot = Gtk.Snapshot.new();
            iconTexture.snapshot(iconPaintableSnapshot, Math.floor(width), Math.floor(height));
            let icon = iconPaintableSnapshot.to_paintable(null);
            icon = this._addEmblemsToIconIfNeeded(icon);
            this._icon.set_paintable(icon);

            return true;
        } catch (e) {
            if (e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                throw e;

            logError(e, `Error while loading ${imageFile.get_uri()}`);
            return false;
        }
    }

    _addEmblemsToIconIfNeeded(iconPaintable) {
        let emblem = null;
        if (this._isDesktopFile && (!this._isValidDesktopFile || !this.trustedDesktopFile))
            emblem = Gio.ThemedIcon.new('emblem-unreadable');

        if (this._isSymlink && (this._desktopManager.showLinkEmblem || this._isBrokenSymlink)) {
            if (this._isBrokenSymlink)
                emblem = Gio.ThemedIcon.new('emblem-unreadable');
            else
                emblem = Gio.ThemedIcon.new('emblem-symbolic-link');
        }

        if (this.isStackTop && !this.stackUnique)
            emblem = Gio.ThemedIcon.new('list-add');

        if (emblem) {
            const scale = this._icon.get_scale_factor();
            let finalSize = Math.floor(Prefs.get_icon_size() / 3) * scale;
            let theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default());
            let emblemIcon = theme.lookup_by_gicon(emblem, finalSize / scale, scale, Gtk.TextDirection.NONE, Gtk.IconLookupFlags.FORCE_SIZE);
            let emblemSnapshot = Gtk.Snapshot.new();
            let iconPaintableSnapshot = Gtk.Snapshot.new();
            emblemIcon.snapshot(emblemSnapshot, emblemIcon.get_intrinsic_width(), emblemIcon.get_intrinsic_height());
            iconPaintable.snapshot(iconPaintableSnapshot, iconPaintable.get_intrinsic_width(), iconPaintable.get_intrinsic_height());
            iconPaintableSnapshot.append_node(emblemSnapshot.to_node());
            return iconPaintableSnapshot.to_paintable(null);
        } else {
            return iconPaintable;
        }
    }

    _createEmblemedIcon(icon, iconName) {
        if (icon === null) {
            if (GLib.path_is_absolute(iconName)) {
                try {
                    let iconFile = Gio.File.new_for_commandline_arg(iconName);
                    icon = new Gio.FileIcon({ file: iconFile });
                } catch (e) {
                    icon = Gio.ThemedIcon.new_with_default_fallbacks(iconName);
                }
            } else {
                icon = Gio.ThemedIcon.new_with_default_fallbacks(iconName);
            }
        }
        let theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default());
        const scale = this._icon.get_scale_factor();
        let iconPaintable = null;
        try {
            iconPaintable = theme.lookup_by_gicon(icon, Prefs.get_icon_size(), scale, Gtk.TextDirection.NONE, Gtk.IconLookupFlags.FORCE_SIZE);
        } catch (e) {
            iconPaintable = theme.lookup_icon('text-x-generic', [], Prefs.get_icon_size(), scale, Gtk.TextDirection.NONE, Gtk.IconLookupFlags.FORCE_SIZE);
        }
        return this._addEmblemsToIconIfNeeded(iconPaintable);
    }

    /** *********************
     * Getters and setters *
     ***********************/

    get state() {
        return this._state;
    }

    set state(state) {
        if (state === this._state)
            return;

        this._state = state;
    }

    get isDrive() {
        return this._fileExtra === Enums.FileType.EXTERNAL_DRIVE;
    }

    get isSelected() {
        return this._isSelected;
    }

    get isSpecial() {
        return this._isSpecial;
    }

    get dropCoordinates() {
        return this._dropCoordinates;
    }

    set dropCoordinates(pos) {
        this._dropCoordinates = pos;
    }
};
Signals.addSignalMethods(desktopIconItem.prototype);
