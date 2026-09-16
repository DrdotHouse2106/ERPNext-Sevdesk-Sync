function show_sync_result(title, result, indicator) {
	const route = "/app/" + frappe.router.slug("SevDesk Sync Log") + "/" + result.log;
	frappe.msgprint({
		title: title,
		message:
			`${frappe.utils.escape_html(result.summary)}<br><br>` +
			`<a href="${route}">${__("Details ansehen")}</a>`,
		indicator: indicator,
	});
}

frappe.ui.form.on("SevDesk Sync Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Verbindung testen"), () => {
			frappe.call({
				method: "sevdesk_sync.tasks.test_connection",
				freeze: true,
				freeze_message: __("Verbindung wird geprüft..."),
			}).then((r) => {
				frappe.msgprint({
					title: __("Verbindungstest"),
					message: r.message,
					indicator: "green",
				});
			});
		});

		frm.add_custom_button(__("Trockenlauf starten"), () => {
			frappe.call({
				method: "sevdesk_sync.tasks.run_dry_run",
				freeze: true,
				freeze_message: __("Trockenlauf läuft..."),
			}).then((r) => {
				show_sync_result(__("Trockenlauf abgeschlossen"), r.message, "blue");
			});
		});

		frm.add_custom_button(__("Jetzt synchronisieren"), () => {
			frappe.confirm(
				__(
					"Preise jetzt wirklich mit sevDesk synchronisieren? Dabei werden ggf. Artikel in sevDesk angelegt oder aktualisiert."
				),
				() => {
					frappe.call({
						method: "sevdesk_sync.tasks.run_sync_now",
						freeze: true,
						freeze_message: __("Synchronisierung läuft..."),
					}).then((r) => {
						frm.reload_doc();
						show_sync_result(__("Synchronisierung abgeschlossen"), r.message, "green");
					});
				}
			);
		});
	},
});
