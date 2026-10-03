
/* Desktop Icons GNOME Shell extension
 *
 * Copyright (C) 2022 Sundeep Mediratta (smedius@gmail.com)
 * Copyright (C) 2019 Sergio Costas (rastersoft@gmail.com)
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

const { Gtk, Gio, GObject } = imports.gi;
const GioSSS = Gio.SettingsSchemaSource;
const Gettext = imports.gettext;

const ExtensionUtils = imports.misc.extensionUtils;
const Me = ExtensionUtils.getCurrentExtension();
const Enums = Me.imports.app.enums;
const PreferencesFrame = Me.imports.app.preferencesFrame;

/**
 * prefs initiation
 *
 * @returns {void}
 */
function init() {
    ExtensionUtils.initTranslations(Me.metadata.uuid);
}

/**
 * prefs widget
 *
 * @returns {Gtk.Widget}
 */
function buildPrefsWidget() {
    let desktopSettings = ExtensionUtils.getSettings();
    let schemaSource = GioSSS.get_default();
    let schemaGtk = schemaSource.lookup(Enums.SCHEMA_GTK, true);
    let gtkSettings = new Gio.Settings({ settings_schema: schemaGtk });
    let schemaNautilus = schemaSource.lookup(Enums.SCHEMA_NAUTILUS, true);
    let nautilusSettings;
    if (!schemaNautilus)
        nautilusSettings = null;
    else
        nautilusSettings = new Gio.Settings({ settings_schema: schemaNautilus });

    const gettext = Gettext.domain(Me.metadata.uuid).gettext;

    const preferencesFrame = new PreferencesFrame.PreferencesFrame(Gtk, GObject, desktopSettings, nautilusSettings, gtkSettings, gettext);
    let frame = preferencesFrame.getFrame();
    frame.show();

    return frame;
}
