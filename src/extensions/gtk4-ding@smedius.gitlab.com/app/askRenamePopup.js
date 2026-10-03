/* DING: Desktop Icons New Generation for GNOME Shell
 *
 * Copyright (C) 2019 Sergio Costas (rastersoft@gmail.com)
 * Based on code original (C) Carlos Soriano
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

const { Gtk, Gio, GLib } = imports.gi;
const DBusUtils = imports.utils.dbusUtils;
const DesktopIconsUtil = imports.utils.desktopIconsUtil;
const FileUtils = imports.utils.fileUtils;
const Gettext = imports.gettext.domain('gtk4-ding');

const _ = Gettext.gettext;

var AskRenamePopup = class {
    constructor(fileItem, allowReturnOnSameName, closeCB) {
        this._validateCancellable = new Gio.Cancellable();
        this._closeCB = closeCB;
        this._allowReturnOnSameName = allowReturnOnSameName;
        this._desktopFile = Gio.File.new_for_path(
            GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP));
        this._fileItem = fileItem;
        this._popover = new Gtk.Popover();
        this._popover.set_autohide(true);
        let contentBox = new Gtk.Grid({
            row_spacing: 6,
            column_spacing: 6,
        });
        contentBox.set_margin_top(10);
        contentBox.set_margin_bottom(10);
        contentBox.set_margin_start(10);
        contentBox.set_margin_end(10);
        this._popover.set_child(contentBox);
        let label = new Gtk.Label({
            label: fileItem.isDirectory ? _('Folder name') : _('File name'),
            justify: Gtk.Justification.LEFT,
            halign: Gtk.Align.START,
        });
        contentBox.attach(label, 0, 0, 2, 1);
        this._textArea = new Gtk.Entry();
        this._textArea.text = fileItem.fileName;
        contentBox.attach(this._textArea, 0, 1, 1, 1);
        this._button = new Gtk.Button({ label: allowReturnOnSameName ? _('OK') : _('Rename') });
        contentBox.attach(this._button, 1, 1, 1, 1);
        this._button.connect('clicked', () => {
            this._do_rename();
        });
        this._textArea.connect('changed', () => {
            this._validate().catch(e => logError(e));
        });
        this._textArea.connect('activate', () => {
            if (this._button.sensitive)
                this._do_rename();
        });
        this._popover.connect('closed', () => {
            this._validateCancellable.cancel();
            closeCB();
        });
        this._textArea.set_activates_default(true);
        this._popover.set_default_widget(this._textArea);
        this._button.get_style_context().add_class('suggested-action');
        contentBox.show();
        this._popover.set_parent(fileItem._grid._window);
        this._popover.set_pointing_to(fileItem.iconRectangle);
        const menuGtkPosition = fileItem._grid.getIntelligentPosition(fileItem.iconRectangle);
        if (menuGtkPosition)
            this._popover.set_position(menuGtkPosition);

        this._popover.popup();
        this._validate().catch(e => logError(e));
        this._textArea.grab_focus_without_selecting();
        this._textArea.select_region(0, DesktopIconsUtil.getFileExtensionOffset(fileItem.fileName, { 'isDirectory': fileItem.isDirectory }).offset);
    }

    async _validate() {
        this._validateCancellable.cancel();
        this._validateCancellable = new Gio.Cancellable();

        let text = this._textArea.text;
        if (!text.length || text.indexOf('/') !== -1) {
            this._button.sensitive = false;
            return;
        }

        if (text === this._fileItem.fileName) {
            this._button.sensitive = !!this._allowReturnOnSameName;
            return;
        }

        let sensitive = true;
        try {
            const finalFile = this._desktopFile.get_child(text);
            if (await FileUtils.queryExists(finalFile, this._validateCancellable))
                sensitive = false;
        } catch (e) {
            if (e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                return;
        }

        this._button.sensitive = sensitive;
    }

    _do_rename() {
        this._popover.popdown();
        this._closeCB();
        if (this._fileItem.fileName === this._textArea.text)
            return;

        DBusUtils.RemoteFileOperations.RenameURIRemote(
            this._fileItem.file.get_uri(), this._textArea.text
        );
    }

    close() {
        this._popover.popdown();
        this._closeCB();
    }

    popupat(fileItem) {
        this._fileItem = fileItem;
        const menuGtkPosition = fileItem._grid.getIntelligentPosition(fileItem.iconRectangle);
        if (menuGtkPosition)
            this._popover.set_position(menuGtkPosition);

        this._popover.set_pointing_to(this._fileItem.iconRectangle);
    }
};
