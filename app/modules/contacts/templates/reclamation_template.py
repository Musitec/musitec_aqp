def build_products_html(products: list | None) -> str:
    if not products:
        return "<p style='color:#64748b;'>Reclamo general sobre la orden</p>"
    html = "<h3 style='color:#334155;margin-top:20px;'>Productos</h3>"
    html += "<ul style='padding-left:20px;color:#334155;'>"
    for p in products:
        name = p.get("name", "Producto")
        option = p.get("selected_option")
        if option:
            name += f" ({option})"
        html += f"<li>{name}</li>"

    html += "</ul>"
    return html

def complaint_created_email_template(
    name: str,
    complaint_id: str,
    order_id: str,
    reason: str,
    support_email: str,
    products: list | None = None
):
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
    products_html = build_products_html(products)
    return f"""
    <html>
    <body style="background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;padding:20px;">
        <div style="max-width:600px;margin:auto;background:#ffffff;padding:30px;border-radius:8px;"> 
            <div style="text-align:center;margin-bottom:20px;">
                <img src="{LOGO_URL}" style="max-width:160px;" />
            </div>
            <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
            <h2 style="color:#334155;">Hemos recibido tu reclamo</h2>
            <p>Hola <strong>{name}</strong>,</p>
            <div style="background:#f1f5f9;padding:15px;border-radius:6px;margin:20px 0;">
                <p><strong>Reclamo:</strong> #{complaint_id}</p>
                <p><strong>Orden:</strong> #{order_id}</p>
                <p><strong>Motivo:</strong> {reason}</p>
            </div>
            {products_html}
            <p>Te notificaremos cuando haya actualizaciones.</p>
            <p>Soporte: <a href="mailto:{support_email}">{support_email}</a></p>
        </div>
    </body>
    </html>
    """

def complaint_update_email_template(
    name: str,
    complaint_id: str,
    old_status: str,
    new_status: str,
    message: str,
    support_email: str,
    products: list | None = None
):
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
    STATUS_LABELS = {
        "open": "Abierto",
        "in_review": "En revisión",
        "resolved": "Resuelto",
        "rejected": "Rechazado"
    }
    old_label = STATUS_LABELS.get(old_status, old_status)
    new_label = STATUS_LABELS.get(new_status, new_status)
    products_html = build_products_html(products)
    return f"""
    <html>
    <body style="background:#f4f4f5;font-family:Arial;padding:20px;">
        <div style="max-width:600px;margin:auto;background:#fff;padding:30px;border-radius:8px;">  
            <div style="text-align:center;margin-bottom:20px;">
                <img src="{LOGO_URL}" style="max-width:160px;" />
            </div>
            <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
            <h2 style="color:#334155;">Actualización de tu reclamo</h2>
            <p>Hola <strong>{name}</strong>,</p>
            <div style="background:#f1f5f9;padding:15px;border-radius:6px;margin:20px 0;">
                <p><strong>ID:</strong> #{complaint_id}</p>
                <p><strong>Estado anterior:</strong> {old_label}</p>
                <p><strong>Estado actual:</strong> {new_label}</p>
            </div>
            <div style="background:#e2e8f0;padding:15px;border-radius:6px;">
                <p><strong>Mensaje del equipo:</strong></p>
                <p>{message}</p>
            </div>
            {products_html}
            <p style="margin-top:20px;">
                Contacto: <a href="mailto:{support_email}">{support_email}</a>
            </p>
        </div>
    </body>
    </html>
    """

def complaint_resolved_email_template(
    name: str,
    complaint_id: str,
    message: str,
    support_email: str,
    products: list | None = None
):
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
    products_html = build_products_html(products)
    return f"""
    <html>
    <body style="background:#f4f4f5;font-family:Arial;padding:20px;">
        <div style="max-width:600px;margin:auto;background:#fff;padding:30px;border-radius:8px;">     
            <div style="text-align:center;margin-bottom:20px;">
                <img src="{LOGO_URL}" style="max-width:160px;" />
            </div>
            <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
            <h2 style="color:#16a34a;">Tu reclamo ha sido resuelto</h2>
            <p>Hola <strong>{name}</strong>,</p>
            <p>Nos alegra informarte que tu reclamo ha sido solucionado.</p>
            <div style="background:#f1f5f9;padding:15px;border-radius:6px;margin:20px 0;">
                <p><strong>ID del reclamo:</strong> #{complaint_id}</p>
            </div>
            <div style="background:#dcfce7;padding:15px;border-radius:6px;">
                <p><strong>Detalle:</strong></p>
                <p>{message}</p>
            </div>
            {products_html}
            <p style="margin-top:20px;">
                Si tienes más dudas, estamos para ayudarte:
                <a href="mailto:{support_email}">{support_email}</a>
            </p>
        </div>
    </body>
    </html>
    """

def complaint_staff_notification_template(
    complaint_id: str,
    user_name: str,
    user_email: str,
    order_id: str,
    reason: str,
    products: list | None
):
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
    products_html = build_products_html(products)
    return f"""
    <html>
    <body style="background:#f4f4f5;font-family:Arial;padding:20px;">
        <div style="max-width:600px;margin:auto;background:#fff;padding:30px;border-radius:8px;">
            <div style="text-align:center;margin-bottom:20px;">
                <img src="{LOGO_URL}" style="max-width:160px;" />
            </div>
            <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
            <h2 style="color:#b91c1c;">Nuevo reclamo recibido</h2>
            <div style="background:#fef2f2;padding:15px;border-radius:6px;margin:20px 0;">
                <p><strong>ID Reclamo:</strong> #{complaint_id}</p>
                <p><strong>Orden:</strong> #{order_id}</p>
            </div>
            <h3 style="color:#334155;">Información del cliente</h3>
            <p><strong>Nombre:</strong> {user_name}</p>
            <p><strong>Email:</strong> {user_email}</p>
            {products_html}
            <h3 style="color:#334155;margin-top:20px;">Motivo del reclamo</h3>
            <div style="background:#f1f5f9;padding:15px;border-radius:6px;">
                <p>{reason}</p>
            </div>
            <p style="font-size:12px;color:#64748b;margin-top:25px;">
                Notificación automática del sistema de reclamos.
            </p>
        </div>
    </body>
    </html>
    """