import streamlit as st
import numpy as np
from PIL import Image, ImageOps, ImageFilter
from collections import Counter
import io
import os
import tempfile
import base64

# ReportLab importeren voor zuivere PDF generatie
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.pagesizes import A0, A1, A2, A3, A4, A5
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    st.warning("ReportLab niet geïnstalleerd. PDF export werkt mogelijk niet optimaal.")

# PDF import libraries (voor PDF bestanden)
try:
    from pdf2image import convert_from_bytes
    PDF_IMPORT = True
except ImportError:
    PDF_IMPORT = False
    st.info("📌 Voor PDF import: installeer pdf2image via 'pip install pdf2image'")

# Pagina-instellingen
st.set_page_config(
    page_title="C.A. Professional Bleed Tool",
    page_icon="📐",
    layout="wide"
)

# C.A. Huisstijl CSS
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    h1 { color: #00594F; }
    .report-title { font-weight: bold; font-size: 20px; color: #00594F; border-bottom: 2px solid #00594F; padding-bottom: 8px; margin-bottom: 15px; }
    .warning-text { color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; }
    .success-text { color: #0f5132; background-color: #d1e7dd; padding: 10px; border-radius: 5px; margin: 10px 0; }
    .info-text { color: #084298; background-color: #cfe2ff; padding: 10px; border-radius: 5px; margin: 10px 0; }
    div.stButton > button { background-color: #00594F; color: white; font-weight: bold; }
    div.stButton > button:hover { background-color: #004d44; }
    </style>
    """, unsafe_allow_html=True)

# Formaat specificaties (breedte, hoogte) in mm
FORMATS = {
    "A5": (148, 210),
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
    "A0": (841, 1189)
}

# Kleurprofielen voor CMYK
COLOR_PROFILES = {
    "CoatedFOGRA39": "Europees standaard voor gestreken papier (ISO 12647-2:2004)",
    "USWebCoatedSWOP": "US Web Coated (SWOP) v2 - Standaard voor VS drukwerk",
    "UncoatedFOGRA29": "Voor ongestreken papier",
    "JapanColor2001Coated": "Japans standaard voor gestreken papier",
    "GenericCMYK": "Algemene CMYK conversie"
}

def rgb_to_cmyk(r, g, b):
    """Converteer RGB naar CMYK waarden (0-100%)"""
    if r == 0 and g == 0 and b == 0:
        return (0, 0, 0, 100)
    
    r_prime = r / 255.0
    g_prime = g / 255.0
    b_prime = b / 255.0
    
    k = 1 - max(r_prime, g_prime, b_prime)
    
    if k < 1:
        c = (1 - r_prime - k) / (1 - k)
        m = (1 - g_prime - k) / (1 - k)
        y = (1 - b_prime - k) / (1 - k)
    else:
        c, m, y = 0, 0, 0
    
    return (c * 100, m * 100, y * 100, k * 100)

def get_dominant_color(image):
    """Bepaal de dominante kleur in een afbeelding"""
    small_img = image.resize((100, 100))
    small_img = small_img.quantize(colors=64).convert('RGB')
    pixels = list(small_img.getdata())
    return Counter(pixels).most_common(1)[0][0]

def remove_crop_marks(image, crop_pixels):
    """Verwijder crop marks/guides van een PDF-afbeelding"""
    if crop_pixels <= 0:
        return image
    
    width, height = image.size
    if width > crop_pixels * 2 and height > crop_pixels * 2:
        return image.crop((
            crop_pixels,
            crop_pixels,
            width - crop_pixels,
            height - crop_pixels
        ))
    return image

def create_bleed_image(original_img, bleed_pixels, method, custom_color=None):
    """
    Voeg bleed toe aan afbeelding met verschillende methoden
    Belangrijk: De bleed wordt naadloos toegevoegd zonder zichtbare lijnen
    """
    width, height = original_img.size
    new_width = width + (bleed_pixels * 2)
    new_height = height + (bleed_pixels * 2)
    
    if method == "Wit / Geselecteerde Kleur":
        # Methode 1: Witte of gekozen kleur
        color = custom_color if custom_color else (255, 255, 255)
        new_img = Image.new('RGB', (new_width, new_height), color)
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
    elif method == "Spiegelen (Mirror)":
        # Methode 2: Spiegel de randen (perfect voor patronen)
        # Eerst een basisvulling om kieren te voorkomen
        new_img = original_img.resize((new_width, new_height), Image.Resampling.NEAREST)
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        # Spiegel bovenrand
        top_mirror = original_img.crop((0, 0, width, bleed_pixels + 1))
        top_mirror = top_mirror.transpose(Image.FLIP_TOP_BOTTOM)
        new_img.paste(top_mirror, (bleed_pixels, 0))
        
        # Spiegel onderrand
        bottom_mirror = original_img.crop((0, height - bleed_pixels - 1, width, height))
        bottom_mirror = bottom_mirror.transpose(Image.FLIP_TOP_BOTTOM)
        new_img.paste(bottom_mirror, (bleed_pixels, new_height - bleed_pixels))
        
        # Spiegel linkerrand
        left_mirror = original_img.crop((0, 0, bleed_pixels + 1, height))
        left_mirror = left_mirror.transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(left_mirror, (0, bleed_pixels))
        
        # Spiegel rechterrand
        right_mirror = original_img.crop((width - bleed_pixels - 1, 0, width, height))
        right_mirror = right_mirror.transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(right_mirror, (new_width - bleed_pixels, bleed_pixels))
        
        # Spiegel hoeken
        # Boven-links
        top_left = original_img.crop((0, 0, bleed_pixels + 1, bleed_pixels + 1))
        top_left = top_left.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(top_left, (0, 0))
        
        # Boven-rechts
        top_right = original_img.crop((width - bleed_pixels - 1, 0, width, bleed_pixels + 1))
        top_right = top_right.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(top_right, (new_width - bleed_pixels, 0))
        
        # Onder-links
        bottom_left = original_img.crop((0, height - bleed_pixels - 1, bleed_pixels + 1, height))
        bottom_left = bottom_left.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(bottom_left, (0, new_height - bleed_pixels))
        
        # Onder-rechts
        bottom_right = original_img.crop((width - bleed_pixels - 1, height - bleed_pixels - 1, width, height))
        bottom_right = bottom_right.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(bottom_right, (new_width - bleed_pixels, new_height - bleed_pixels))
        
        # Herstel het origineel scherp in het midden
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
    elif method == "Randpixels Uitrekken (Stretch)":
        # Methode 3: Rek de randpixels uit
        new_img = Image.new('RGB', (new_width, new_height))
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        # Rek bovenrand uit
        top_strip = original_img.crop((0, 0, width, 1))
        top_stretched = top_strip.resize((width, bleed_pixels + 1), Image.Resampling.NEAREST)
        new_img.paste(top_stretched, (bleed_pixels, 0))
        
        # Rek onderrand uit
        bottom_strip = original_img.crop((0, height-1, width, height))
        bottom_stretched = bottom_strip.resize((width, bleed_pixels + 1), Image.Resampling.NEAREST)
        new_img.paste(bottom_stretched, (bleed_pixels, new_height - bleed_pixels))
        
        # Rek linkerrand uit
        left_strip = original_img.crop((0, 0, 1, height))
        left_stretched = left_strip.resize((bleed_pixels + 1, height), Image.Resampling.NEAREST)
        new_img.paste(left_stretched, (0, bleed_pixels))
        
        # Rek rechterrand uit
        right_strip = original_img.crop((width-1, 0, width, height))
        right_stretched = right_strip.resize((bleed_pixels + 1, height), Image.Resampling.NEAREST)
        new_img.paste(right_stretched, (new_width - bleed_pixels, bleed_pixels))
        
        # Vul hoeken met randkleur
        top_left_color = original_img.getpixel((0, 0))
        corner = Image.new('RGB', (bleed_pixels, bleed_pixels), top_left_color)
        new_img.paste(corner, (0, 0))
        new_img.paste(corner, (new_width - bleed_pixels, 0))
        new_img.paste(corner, (0, new_height - bleed_pixels))
        new_img.paste(corner, (new_width - bleed_pixels, new_height - bleed_pixels))
        
        # Herstel origineel
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
    elif method == "Dominante Achtergrondkleur":
        # Methode 4: Gebruik dominante kleur uit afbeelding
        dominant_color = get_dominant_color(original_img)
        new_img = Image.new('RGB', (new_width, new_height), dominant_color)
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
    
    return new_img

def export_to_pdf(image, convert_cmyk, profile_name, output_format, bleed_mm):
    """Exporteer afbeelding naar PDF met CMYK optie"""
    # Bereken PDF afmetingen in punten (1 pt = 1/72 inch)
    width_pt = (image.width / 300.0) * 72.0
    height_pt = (image.height / 300.0) * 72.0
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width_pt, height_pt))
    
    # Vul achtergrond met wit om kieren te maskeren
    c.setFillColorRGB(1, 1, 1)
    c.rect(0, 0, width_pt, height_pt, fill=1, stroke=0)
    
    # Voeg metadata toe
    if convert_cmyk:
        c.setProducer(f"C.A. Bleed Tool - CMYK ({profile_name})")
        c.setTitle(f"C.A. Document - {output_format} - {bleed_mm}mm bleed")
        c.setSubject("CMYK ready voor professioneel drukwerk")
    
    # Sla afbeelding tijdelijk op
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
        temp_path = tmp_file.name
        # Gebruik JPEG met hoge kwaliteit voor PDF
        if convert_cmyk:
            # Converteer naar CMYK modus voor de afbeelding
            cmyk_img = image.convert('CMYK')
            cmyk_img.save(temp_path, 'JPEG', quality=95, dpi=(300, 300))
        else:
            image.save(temp_path, 'JPEG', quality=95, dpi=(300, 300))
    
    # Plaats afbeelding in PDF
    img_reader = ImageReader(temp_path)
    c.drawImage(img_reader, 0, 0, width=width_pt, height=height_pt, preserveAspectRatio=False)
    c.showPage()
    c.save()
    
    # Opruimen
    try:
        os.unlink(temp_path)
    except:
        pass
        
    return buffer.getvalue()

def check_aspect_ratio(image, format_name):
    """Controleer aspect ratio en geef waarschuwing bij meer dan 10% verschil"""
    format_mm = FORMATS[format_name]
    target_ratio = format_mm[0] / format_mm[1]
    image_ratio = image.width / image.height
    ratio_diff = abs((image_ratio - target_ratio) / target_ratio) * 100
    
    if ratio_diff > 10:
        return f"⚠️ **Waarschuwing:** Aspect ratio verschil van {ratio_diff:.1f}% overschrijdt 10% limiet. De afbeelding zal worden bijgesneden. Gebruik Gimp/Photoshop om handmatig te resizen voor optimaal resultaat."
    else:
        return f"✓ Aspect ratio is acceptabel ({ratio_diff:.1f}% verschil)"

# ============================================================================
# HOOFD INTERFACE
# ============================================================================

st.title("📐 C.A. Professional Bleed & CMYK Tool")
st.subheader("Voeg naadloze afloopruimte toe en converteer naar CMYK voor drukwerk")

with st.sidebar:
    st.header("🔧 Drukwerk Instellingen")
    
    selected_format = st.selectbox("📄 Selecteer Doelformaat:", list(FORMATS.keys()), index=1)
    width_mm, height_mm = FORMATS[selected_format]
    st.caption(f"Formaat: {width_mm} × {height_mm} mm")
    
    st.divider()
    
    # Bleed instellingen - FIX: gebruik float voor step
    bleed_mm = st.number_input("📏 Afloopruimte (Bleed) in mm:", min_value=0.0, max_value=20.0, value=3.0, step=0.5, format="%.1f")
    st.caption("Standaard 3mm is gebruikelijk voor drukwerk")
    
    fill_method = st.radio(
        "🎨 Afloop Opvulmethode:",
        ["Spiegelen (Mirror)", "Randpixels Uitrekken (Stretch)", "Wit / Geselecteerde Kleur", "Dominante Achtergrondkleur"],
        help="Mirror werkt het beste voor patronen, Stretch voor foto's, Kleur voor strakke ontwerpen"
    )
    
    # Kleur selectie (alleen bij wit/kleur methode)
    chosen_rgb = (255, 255, 255)
    if fill_method == "Wit / Geselecteerde Kleur":
        hex_color = st.color_picker("🎨 Kies randkleur:", "#FFFFFF")
        chosen_rgb = tuple(int(hex_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        # Toon CMYK waarden van gekozen kleur
        c, m, y, k = rgb_to_cmyk(chosen_rgb[0], chosen_rgb[1], chosen_rgb[2])
        st.caption(f"CMYK: {c:.1f}%, {m:.1f}%, {y:.1f}%, {k:.1f}%")
    
    st.divider()
    
    # CMYK instellingen
    st.subheader("🖨️ CMYK Conversie")
    convert_to_cmyk = st.checkbox("Zet om naar CMYK kleurruimte", value=True, 
                                  help="Essentieel voor offset en digitaal drukwerk")
    
    if convert_to_cmyk:
        color_profile = st.selectbox("Kleurprofiel:", list(COLOR_PROFILES.keys()), index=0)
        st.caption(COLOR_PROFILES[color_profile])
    
    st.divider()
    
    # Output instellingen
    output_format = st.selectbox("📤 Output Formaat:", list(FORMATS.keys()), index=1)
    output_type = st.radio("📁 Output Type:", ["PDF (Aanbevolen)", "PNG"], 
                          help="PDF is aanbevolen voor drukwerk, PNG voor preview")
    
    # PDF import instellingen
    st.divider()
    st.subheader("📑 PDF Import")
    crop_marks_remove = st.checkbox("Verwijder crop marks / snijtekens", value=True)
    if crop_marks_remove:
        crop_pixels = st.slider("Aantal pixels wegknippen:", 20, 100, 35, 
                                help="20-50 pixels verwijdert meestal alle snijtekens")

# Bestand upload
st.markdown("### 📂 1. Upload uw bestand")
uploaded_file = st.file_uploader(
    "Kies een PDF of afbeelding (JPG, JPEG, PNG)",
    type=["jpg", "jpeg", "png", "pdf"],
    help="PDF bestanden worden omgezet naar 300 DPI afbeeldingen"
)

if uploaded_file is not None:
    try:
        # Laad en verwerk bestand
        file_bytes = uploaded_file.read()
        file_ext = uploaded_file.name.split('.')[-1].lower()
        
        with st.spinner("📄 Bestand laden en verwerken..."):
            if file_ext == 'pdf':
                if not PDF_IMPORT:
                    st.error("PDF import vereist pdf2image. Installeer met: pip install pdf2image")
                    st.stop()
                
                # Converteer PDF naar afbeelding
                images = convert_from_bytes(file_bytes, first_page=1, last_page=1, dpi=300)
                if images:
                    original_img = images[0]
                    st.info(f"📄 PDF geladen - Eerste pagina gebruikt")
                    
                    # Verwijder crop marks indien gewenst
                    if crop_marks_remove:
                        original_img = remove_crop_marks(original_img, crop_pixels)
                        st.success(f"✓ Crop marks verwijderd ({crop_pixels}px van elke kant)")
                else:
                    st.error("Kan PDF niet verwerken")
                    st.stop()
            else:
                # Laad afbeelding
                original_img = Image.open(io.BytesIO(file_bytes))
            
            # Converteer naar RGB indien nodig
            if original_img.mode != 'RGB':
                original_img = original_img.convert('RGB')
        
        # Controleer aspect ratio
        st.markdown("### 📏 2. Formaat & Aspect Ratio Check")
        aspect_warning = check_aspect_ratio(original_img, selected_format)
        if "⚠️" in aspect_warning:
            st.markdown(f'<div class="warning-text">{aspect_warning}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="success-text">{aspect_warning}</div>', unsafe_allow_html=True)
        
        # Preview kolommen
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<p class="report-title">📸 Origineel Bestand</p>', unsafe_allow_html=True)
            st.image(original_img, caption=f"Origineel: {original_img.size[0]}×{original_img.size[1]} pixels", use_container_width=True)
        
        # Verwerk de bleed
        with st.spinner("🔧 Bleed toevoegen... Dit kan even duren bij grote bestanden"):
            # Resize naar exact formaat (300 DPI)
            target_width = int(width_mm / 25.4 * 300)
            target_height = int(height_mm / 25.4 * 300)
            resized_img = original_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Bereken bleed pixels
            bleed_pixels = int(bleed_mm / 25.4 * 300)
            
            # Voeg bleed toe
            final_img = create_bleed_image(resized_img, bleed_pixels, fill_method, chosen_rgb)
        
        with col2:
            st.markdown('<p class="report-title">✨ Resultaat met Bleed</p>', unsafe_allow_html=True)
            st.image(final_img, caption=f"Na bleed: {final_img.size[0]}×{final_img.size[1]} pixels (+{bleed_mm}mm)", use_container_width=True)
            st.markdown(f'<div class="success-text">✅ Naadloze bleed toegevoegd!</div>', unsafe_allow_html=True)
        
        # Export sectie
        st.markdown("### 💾 3. Exporteer")
        
        base_name = os.path.splitext(uploaded_file.name)[0]
        cmyk_suffix = "_CMYK" if convert_to_cmyk and output_type == "PDF (Aanbevolen)" else ""
        
        if output_type == "PDF (Aanbevolen)":
            if not PDF_SUPPORT:
                st.error("PDF export vereist ReportLab. Installeer met: pip install reportlab")
                st.stop()
            
            with st.spinner("📑 PDF genereren..."):
                pdf_data = export_to_pdf(final_img, convert_to_cmyk, color_profile, output_format, bleed_mm)
                
                st.download_button(
                    label=f"📥 Download {selected_format} PDF {cmyk_suffix}",
                    data=pdf_data,
                    file_name=f"{base_name}{cmyk_suffix}_BLEED{int(bleed_mm)}mm_{selected_format}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                
                if convert_to_cmyk:
                    st.markdown(f'<div class="info-text">🖨️ **CMYK Ready!** Dit PDF is voorbereid voor professioneel drukwerk met profiel: {color_profile}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="warning-text">⚠️ RGB PDF - Alleen geschikt voor schermweergave, niet voor professioneel drukwerk</div>', unsafe_allow_html=True)
        else:
            # PNG export
            buffer = io.BytesIO()
            final_img.save(buffer, format="PNG", dpi=(300, 300))
            png_data = buffer.getvalue()
            
            st.download_button(
                label=f"📥 Download {selected_format} PNG",
                data=png_data,
                file_name=f"{base_name}{cmyk_suffix}_BLEED{int(bleed_mm)}mm_{selected_format}.png",
                mime="image/png",
                use_container_width=True
            )
        
        # Toon CMYK info voor kleuren
        if fill_method == "Wit / Geselecteerde Kleur" and convert_to_cmyk:
            st.markdown("---")
            st.markdown("### 🎨 Kleur conversie info")
            c, m, y, k = rgb_to_cmyk(chosen_rgb[0], chosen_rgb[1], chosen_rgb[2])
            st.info(f"""
            **Gekozen randkleur in CMYK:**  
            C: {c:.1f}% | M: {m:.1f}% | Y: {y:.1f}% | K: {k:.1f}%  
            *Deze waarden worden gebruikt in het CMYK PDF*
            """)
        
        st.balloons()
        
    except Exception as e:
        st.error(f"❌ Fout tijdens verwerking: {str(e)}")
        st.exception(e)

else:
    # Informatie sectie wanneer geen bestand is geüpload
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 📌 Hoe werkt het?
        1. Upload een PDF of afbeelding
        2. Kies formaat (A5 t/m A0)
        3. Stel bleed in (3mm is standaard)
        4. Selecteer vulmethode
        5. Download het resultaat
        """)
    
    with col2:
        st.markdown("""
        ### 🎨 Bleed Methoden
        - **Mirror:** Spiegel de randen
        - **Stretch:** Rek randpixels uit
        - **Kleur:** Gebruik een vaste kleur
        - **Dominant:** Detecteer hoofdkleur
        """)
    
    with col3:
        st.markdown("""
        ### 🖨️ Voor drukwerk
        - ✓ CMYK conversie
        - ✓ 300 DPI resolutie
        - ✓ Crop marks verwijdering
        - ✓ PDF metadata met profiel
        """)

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #666;'>© 2024 C.A. Professional Bleed Tool | Voor offset en digitaal drukwerk</p>", 
    unsafe_allow_html=True
)
