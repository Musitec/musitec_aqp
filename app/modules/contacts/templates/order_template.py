EMAIL_WRAPPER_START = """
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            <style> @media only screen and (max-width:780px){
                .container{ width:95% !important; padding:20px !important; }
                .product-name{ font-size:13px !important; }
                .price-normal{ display:none !important; }
                .img-cell img{ width:40px !important; height:40px !important; } }
            </style>
        </head>
    <body style="margin:0;padding:0;background:#f4f4f5;">
        <table role="presentation" width="100%" height="100%"
            style="border-collapse:collapse;"> <tr> <td align="center"
            valign="middle">
        <table role="presentation" 
            class="container" width="600" style="max-width:600px;background:#ffffff;padding:30px;border-radius:8px;
                box-shadow:0 4px 10px rgba(0,0,0,0.05); font-family:Arial,Helvetica,sans-serif;"> 
            """
EMAIL_WRAPPER_END = """
    </table> 
    </td>
    </tr>
    </table>
    </body>
    </html>"""
def truncate(text, max_len=30):
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."
def _order_rows_html(order: dict) -> str:
    rows_html = ""
    for item in order["items"]:
        img_url = item["image"]
        product_display_name = item["name"]
        rows_html += f"""
        <tr>
            <td class="img-cell" style="padding:10px;border-radius:6px;width:50px;height:50px;background-color:#ffffff;">
                <img src="{img_url}" alt="{product_display_name}" style="max-width:100%;max-height:100%" />
            </td>
            <td class="product-name" style="padding:10px 5px;color:#334155;font-size:14px;">{truncate(product_display_name)} </td>
        <td style="padding:10px 5px;text-align:center;color:#334155;"> {item["quantity"]} </td>
        <td class="price-normal" style="padding:10px 5px;text-align:right;">
            <span style="color:#94a3b8;text-decoration:line-through;font-size:13px;"> 
                S/ {item["quantity"]*item["unit_price"]:.2f}
            </span>
        </td>
        <td style="padding:10px 5px;text-align:right;">
            <span style="color:#16a34a;font-weight:600;">
                S/ {item["subtotal_discounted"]:.2f}
            </span>
        </td>
        </tr>"""
    return rows_html
def order_email_template(user_name: str, order: dict):
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
    rows_html = _order_rows_html(order)
    return EMAIL_WRAPPER_START + f"""
        <tr> <td align="center">
        <img src="{LOGO_URL}" style="max-width:160px;height:auto;margin-bottom:20px;" />
        <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
        <h2 style="color:#334155;margin-bottom:5px;">Confirmación de pedido</h2>
        <p style="color:#475569;margin-top:0;"> Hola <strong>{user_name}</strong>,
        gracias por tu orden. </p> <div style="margin-top:10px;color:#64748b;font-size:13px;">
        Código de orden: <strong>{order["code"]}</strong>
        </div> <table width="100%" style="border-collapse:collapse;margin-top:20px;">
        <thead> <tr style="border-bottom:1px solid #e5e7eb;">
        <th></th>
        <th style="text-align:left;color:#64748b;font-size:12px;">Producto</th>
        <th style="text-align:center;color:#64748b;font-size:12px;">Cant.</th>
        <th class="price-normal" style="text-align:right;color:#64748b;font-size:12px;">
        Precio normal</th>
        <th style="text-align:right;color:#64748b;font-size:12px;">Precio con descuento</th>
        </tr>
        </thead>
        <tbody> {rows_html} </tbody>
        </table>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;" />
            <table width="100%" style="font-size:14px;color:#334155;">
            <tr>
                <td>Total sin descuento:</td>
                <td style="text-align:right;color:#94a3b8;text-decoration:line-through;"> S/ {order["total_raw"]:.2f}</td>
            </tr>
            <tr>
                <td style="padding-top:6px;font-weight:600;">Total pagado:</td>
                <td style="text-align:right;color:#16a34a;font-weight:700;padding-top:6px;"> S/ {order["total_discounted"]:.2f}</td>
            </tr>
        </table>
        <p style="font-size:12px;color:#64748b;margin-top:25px;">
            Nos contactaremos contigo para el envío.
        </p>
    </td></tr> """ + EMAIL_WRAPPER_END
def admin_order_email_template(user_name: str, user_email: str, user_phone: str, order: dict):
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
    rows_html = _order_rows_html(order)
    return EMAIL_WRAPPER_START + f""" <tr>
    <td align="center">
        <img src="{LOGO_URL}"style="max-width:160px;height:auto;margin-bottom:20px;" />
        <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
        <h2 style="color:#334155;margin-bottom:5px;"> Nueva orden recibida </h2>
        <p style="color:#475569;margin-top:0;"> Se ha creado una nueva orden en la tienda. </p>
        <table width="100%" style="margin-top:20px;">
            <tr>
                <td style="padding:15px;background:#f1f5f9;border-radius:6px; color:#334155;line-height:1.5;font-size:14px;">
                    <strong>Nueva orden:</strong> {order["code"]}
                <br/><br/> <strong>Usuario que hizo la orden:</strong><br/> {user_name}<br/>
            <span style="color:#64748b;">
                Correo: {user_email}
            </span>
            <br/> <span style="color:#64748b;"> Número telefónico: {user_phone}
            </span>
            </td>
            </tr>
        </table>
        <table width="100%" style="border-collapse:collapse;margin-top:20px;">
            <thead> <tr style="border-bottom:1px solid #e5e7eb;">
            <th></th>
            <th style="text-align:left;color:#64748b;font-size:12px;">Producto</th>
            <th style="text-align:center;color:#64748b;font-size:12px;">Cant.</th>
            <th class="price-normal" style="text-align:right;color:#64748b;font-size:12px;"> Precio normal </th>
            <th style="text-align:right;color:#64748b;font-size:12px;"> Precio con descuento </th>
            </tr> </thead> <tbody> {rows_html} </tbody>
        </table>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;" />
            <table width="100%" style="font-size:14px;color:#334155;">
                <tr>
                <td>Total sin descuento:</td>
                <td style="text-align:right;color:#94a3b8;text-decoration:line-through;"> S/ {order["total_raw"]:.2f}</td></tr>
                <tr>
                <td style="padding-top:6px;font-weight:600;"> Total con descuento: </td>
                <td style="text-align:right;color:#16a34a;font-weight:700;padding-top:6px;"> S/ {order["total_discounted"]:.2f} </td></tr>
            </table>
            <p style="font-size:12px;color:#64748b;margin-top:25px;">
            Notificación automática del sistema de pedidos. </p> </td> </tr> """ + EMAIL_WRAPPER_END 

def order_cancelled_email_client_template(user_name: str, order: dict): 
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
    rows_html = _order_rows_html(order)
    return EMAIL_WRAPPER_START + f"""
    <tr>
        <td align="center">
        <img src="{LOGO_URL}" style="max-width:160px;height:auto;margin-bottom:20px;" />
        <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
        <h2 style="color:#dc2626;margin-bottom:5px;"> Pedido cancelado </h2>
        <p style="color:#475569;margin-top:0;"> Hola <strong>{user_name}</strong>, tu pedido ha sido cancelado. </p>
        <div style="margin-top:10px;color:#64748b;font-size:13px;"> ID de orden: <strong>{order["code"]}</strong> </div>
        <table width="100%" style="border-collapse:collapse;margin-top:20px;">
            <thead> <tr style="border-bottom:1px solid #e5e7eb;">
                <th></th>
                <th style="text-align:left;color:#64748b;font-size:12px;">Producto</th>
                <th style="text-align:center;color:#64748b;font-size:12px;">Cant.</th>
                <th class="price-normal" style="text-align:right;color:#64748b;font-size:12px;">Precio normal</th>
                <th style="text-align:right;color:#64748b;font-size:12px;">Precio con descuento</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;" />
        <table width="100%" style="font-size:14px;color:#334155;">
            <tr>
                <td>Total del pedido cancelado:</td>
                <td style="text-align:right;color:#dc2626;font-weight:700;"> S/ {order["total_discounted"]:.2f}</td>
            </tr>
        </table>
        <p style="font-size:12px;color:#64748b;margin-top:25px;">
            Si tienes alguna duda puedes responder a este correo.
        </p>
    </td>
    </tr> """ + EMAIL_WRAPPER_END
def order_cancelled_email_staff_template(user_name: str, order: dict):
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
    rows_html = _order_rows_html(order)
    return EMAIL_WRAPPER_START + f"""
    <tr>
        <td align="center">
        <img src="{LOGO_URL}" style="max-width:160px;height:auto;margin-bottom:20px;" />
        <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
        <h2 style="color:#dc2626;margin-bottom:5px;"> Pedido cancelado </h2>
        <p style="color:#475569;margin-top:0;"> El usuario <strong>{user_name}</strong> canceló su pedido. </p>
        <div style="margin-top:10px;color:#64748b;font-size:13px;"> ID de orden: <strong>{order["code"]}</strong>
        </div> <table width="100%" style="border-collapse:collapse;margin-top:20px;">
        <thead>
            <tr style="border-bottom:1px solid #e5e7eb;">
                <th></th>
                <th style="text-align:left;color:#64748b;font-size:12px;">Producto</th>
                <th style="text-align:center;color:#64748b;font-size:12px;">Cant.</th>
                <th class="price-normal" style="text-align:right;color:#64748b;font-size:12px;">Precio normal</th>
                <th style="text-align:right;color:#64748b;font-size:12px;">Precio con descuento</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
        </table>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;" />
            <table width="100%" style="font-size:14px;color:#334155;">
                <tr>
                    <td>Total del pedido cancelado:</td>
                    <td style="text-align:right;color:#dc2626;font-weight:700;"> S/ {order["total_discounted"]:.2f}</td>
                </tr>
            </table>
            <p style="font-size:12px;color:#64748b;margin-top:25px;"> Perdone las molestias. </p>
            </td>
            </tr> """ + EMAIL_WRAPPER_END
def order_delivered_email_template(user_name: str, order: dict):
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
    rows_html = _order_rows_html(order)
    return EMAIL_WRAPPER_START + f"""
    <tr>
        <td align="center">
            <img src="{LOGO_URL}" style="max-width:160px;height:auto;margin-bottom:20px;" />
            <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
            <h2 style="color:#16a34a;margin-bottom:5px;"> Pedido entregado </h2>
            <p style="color:#475569;margin-top:0;"> Hola <strong>{user_name}</strong>, tu pedido ha sido entregado correctamente.</p>
            <div style="margin-top:10px;color:#64748b;font-size:13px;"> ID de orden: <strong>{order["code"]}</strong> </div>
            <table width="100%" style="border-collapse:collapse;margin-top:20px;">
                <thead>
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <th></th>
                        <th style="text-align:left;color:#64748b;font-size:12px;">Producto</th>
                        <th style="text-align:center;color:#64748b;font-size:12px;">Cant.</th>
                        <th class="price-normal" style="text-align:right;color:#64748b;font-size:12px;">Precio normal</th>
                        <th style="text-align:right;color:#64748b;font-size:12px;">Precio con descuento</th>
                    </tr>
                </thead>
                <tbody> {rows_html} </tbody>
            </table>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;" />
                <table width="100%" style="font-size:14px;color:#334155;">
                    <tr>
                        <td>Total pagado:</td>
                        <td style="text-align:right;color:#16a34a;font-weight:700;"> S/ {order["total_discounted"]:.2f}</td>
                    </tr>
                </table>
                <p style="font-size:12px;color:#64748b;margin-top:25px;"> Gracias por tu compra. Esperamos verte nuevamente. </p>
                </td> </tr> """ + EMAIL_WRAPPER_END