/* Desktop Icons GNOME Shell extension
 *
 * Copyright (C) 2022 Sundeep Mediratta (smedius@gmail.com)
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

var PreferencesFrame = class {
    constructor(Gtk, GObject, desktopSettings, nautilusSettings, gtkSettings, getTextDomain) {
        this._Gtk = Gtk;
        this._GObject = GObject;
        this.desktopSettings = desktopSettings;
        this.nautilusSettings = nautilusSettings;
        this.gtkSettings = gtkSettings;
        this._ = getTextDomain;
    }

    getFrame() {
        const frame = new this._Gtk.Box({ orientation: this._Gtk.Orientation.VERTICAL });
        frame.set_spacing(10);
        frame.set_margin_top(10);
        frame.set_margin_bottom(10);
        frame.set_margin_start(10);
        frame.set_margin_end(10);

        if (!frame.append)
            frame.append = frame.add;

        frame.append(this.buildSelector(this.desktopSettings, 'icon-size', this._('Size for the desktop icons'), { 'tiny': this._('Tiny'), 'small': this._('Small'), 'standard': this._('Standard'), 'large': this._('Large') }));
        frame.append(this.buildSwitcher(this.desktopSettings, 'show-home', this._('Show the personal folder in the desktop')));
        frame.append(this.buildSwitcher(this.desktopSettings, 'show-trash', this._('Show the trash icon in the desktop')));
        frame.append(this.buildSwitcher(this.desktopSettings, 'show-volumes', this._('Show external drives in the desktop')));
        frame.append(this.buildSwitcher(this.desktopSettings, 'show-network-volumes', this._('Show network drives in the desktop')));
        frame.append(this.buildSelector(this.desktopSettings,
            'start-corner',
            this._('New icons alignment'),
            {
                'top-left': this._('Top-left corner'),
                'top-right': this._('Top-right corner'),
                'bottom-left': this._('Bottom-left corner'),
                'bottom-right': this._('Bottom-right corner'),
            }));
        frame.append(this.buildSwitcher(this.desktopSettings, 'add-volumes-opposite', this._('Add new drives to the opposite side of the screen')));
        frame.append(this.buildSwitcher(this.desktopSettings, 'show-drop-place', this._("Highlight the drop place during Drag'n'Drop")));
        frame.append(this.buildSwitcher(this.desktopSettings, 'use-nemo', this._('Use Nemo to open folders')));
        frame.append(this.buildSwitcher(this.desktopSettings, 'show-link-emblem', this._('Add an emblem to soft links')));
        frame.append(this.buildSwitcher(this.desktopSettings, 'dark-text-in-labels', this._('Use dark text in icon labels')));
        frame.append(new this._Gtk.Separator({ orientation: this._Gtk.Orientation.HORIZONTAL }));

        // Nautilus Options
        const frameLabel = new this._Gtk.Label({
            label: `<b>${this._('Settings shared with Nautilus')}</b>`,
            use_markup: true,
        });
        const nautilusFrame = new this._Gtk.Frame({ label_widget: frameLabel });
        const nautilusBox = new this._Gtk.Box({ orientation: this._Gtk.Orientation.VERTICAL, spacing: 10 });
        nautilusBox.set_margin_top(5);
        nautilusBox.set_margin_bottom(5);
        nautilusBox.set_margin_start(5);
        nautilusBox.set_margin_end(5);
        nautilusFrame.set_child(nautilusBox);
        frame.append(nautilusFrame);

        if (!nautilusBox.append)
            nautilusBox.append = nautilusBox.add;

        nautilusBox.append(this.buildSelector(this.nautilusSettings, 'click-policy', this._('Click type for open files'), { 'single': this._('Single click'), 'double': this._('Double click') }));
        nautilusBox.append(this.buildSwitcher(this.gtkSettings, 'show-hidden', this._('Show hidden files')));
        nautilusBox.append(this.buildSwitcher(this.nautilusSettings, 'show-delete-permanently', this._('Show a context menu item to delete permanently')));
        // Gnome Shell 40 removed this option
        try {
            nautilusBox.append(this.buildSelector(this.nautilusSettings,
                'executable-text-activation',
                this._('Action to do when launching a program from the desktop'), {
                    'display': this._('Display the content of the file'),
                    'launch': this._('Launch the file'),
                    'ask': this._('Ask what to do'),
                }));
        } catch (e) {}

        nautilusBox.append(this.buildSelector(this.nautilusSettings,
            'show-image-thumbnails',
            this._('Show image thumbnails'), {
                'never': this._('Never'),
                'local-only': this._('Local files only'),
                'always': this._('Always'),
            }));

        return frame;
    }

    buildSwitcher(settings, key, labelText) {
        const hbox = new this._Gtk.Box({ orientation: this._Gtk.Orientation.HORIZONTAL, spacing: 10 });
        hbox.set_hexpand(true);
        const label = new this._Gtk.Label({ label: labelText, xalign: 0 });
        const switcher = new this._Gtk.Switch({ active: settings.get_boolean(key) });
        label.set_hexpand(true);
        switcher.set_hexpand(false);
        switcher.set_halign(this._Gtk.Align.END);
        settings.bind(key, switcher, 'active', 3);
        if (hbox.pack_start) {
            hbox.pack_start(label, true, true, 0);
            hbox.add(switcher);
        } else {
            hbox.append(label);
            hbox.append(switcher);
        }

        return hbox;
    }

    buildSelector(settings, key, labelText, elements) {
        const listStore = new this._Gtk.ListStore();
        listStore.set_column_types([this._GObject.TYPE_STRING, this._GObject.TYPE_STRING]);
        let schemaKey = settings.settings_schema.get_key(key);
        let values = schemaKey.get_range().get_child_value(1).get_child_value(0).get_strv();
        for (let val of values) {
            let iter = listStore.append();
            let visibleText = val;
            if (visibleText in elements)
                visibleText = elements[visibleText];
            listStore.set(iter, [0, 1], [visibleText, val]);
        }
        const hbox = new this._Gtk.Box({ orientation: this._Gtk.Orientation.HORIZONTAL, spacing: 10 });
        hbox.set_hexpand(true);
        const label = new this._Gtk.Label({ label: labelText, xalign: 0 });
        label.set_hexpand(true);
        const combo = new this._Gtk.ComboBox({ model: listStore });
        combo.set_hexpand(false);
        combo.set_halign(this._Gtk.Align.END);
        let rendererText = new this._Gtk.CellRendererText();
        combo.pack_start(rendererText, false);
        combo.add_attribute(rendererText, 'text', 0);
        combo.set_id_column(1);
        settings.bind(key, combo, 'active-id', 3);
        if (hbox.pack_start) {
            hbox.pack_start(label, true, true, 0);
            hbox.add(combo);
        } else {
            hbox.append(label);
            hbox.append(combo);
        }
        return hbox;
    }
};
