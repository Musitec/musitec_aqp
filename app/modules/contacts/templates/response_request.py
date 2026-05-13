def response_email_template():
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"

    return f"""
    <html>
    <body style="background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;padding:20px;">
        <div style="
            max-width:600px;
            margin:auto;
            background:#ffffff;
            padding:30px;
            border-radius:8px;
            box-shadow:0 4px 10px rgba(0,0,0,0.05);
        ">
            <div style="text-align:center;margin-bottom:20px;">
                <img src="{LOGO_URL}" alt="Logo Musitec"
                     style="max-width:160px;height:auto;" />
            </div>
            <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
            <h2 style="color:#334155;margin-bottom:10px;">
                ¡Hemos recibido tu mensaje!
            </h2>
            <p style="color:#475569;line-height:1.6;">
                Gracias por ponerte en contacto con nosotros. Tu solicitud ha sido recibida
                correctamente a través de nuestro formulario web.
            </p>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;" />
            <div style="
                margin-top:20px;
                padding:15px;
                background:#f8fafc;
                border-left:4px solid #2563eb;
                color:#334155;
                line-height:1.6;
            ">
                Nuestro equipo revisará tu mensaje y se pondrá en contacto contigo
                a la brevedad para ayudarte a resolver tus dudas.
            </div>
            <p style="color:#475569;margin-top:20px;">
                Agradecemos tu interés y confianza.
            </p>
            <p style="font-size:12px;color:#64748b;margin-top:25px;">
                Este mensaje fue enviado automáticamente.  
                Por favor, no respondas a este correo.
            </p>
        </div>
    </body>
    </html>
    """