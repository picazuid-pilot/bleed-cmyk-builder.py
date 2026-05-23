import streamlit as st
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageDraw
from collections import Counter
import io
import os
import tempfile

# ReportLab importeren voor zuivere PDF generatie
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.pagesizes import A0, A1, A2, A3, A4, A5
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    st.warning("ReportLab niet geïnstalleerd. PDF export werkt mogelijk niet optimaal.")

# PDF import libraries
try:
    from pdf2image import convert_from_bytes
    PDF_IMPORT = True
except ImportError:
    PDF_IMPORT = False
    st.info("📌 Voor PDF import: pip install pdf2image")

# Pagina-instellingen
st.set_page_config(
    page_title="C.A. Professional Bleed Tool - Haarlijn Vrij",
    page_icon="📐",
    layout="wide"
)

# CSS
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

# Formaat specificaties (mm)
FORMATS = {
    "A5": (148, 210),
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
    "A0": (841, 1189)
}

# Kleurprofielen
COLOR_PROFILES = {
    "CoatedFOGRA39": "Europees standaard voor gestreken papier",
    "USWebCoatedSWOP": "US Web Coated SWOP - VS standaard",
    "UncoatedFOGRA29": "Voor ongestreken papier",
    "JapanColor2001Coated": "Japans standaard",
    "GenericCMYK": "Algemene CMYK conversie"
}

def rgb_to_cmyk(r, g, b):
    """RGB naar CMYK (0-100%)"""
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
    """Bepaal dominante kleur"""
    small_img = image.resize((100, 100))
    small_img = small_img.quantize(colors=64).convert('RGB')
    pixels = list(small_img.getdata())
    return Counter(pixels).most_common(1)[0][0]

def remove_crop_marks(image, crop_pixels):
    """Verwijder crop marks van PDF"""
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

def create_seamless_bleed(original_img, bleed_pixels, method, custom_color=None):
    """
    CREËERT EEN HAARLIJN-VRIJE BLEED
    Fixes:
    1. Geen resize() als basis - voorkomt interpolatie artifacts
    2. Geen +1 overlap pixels - voorkomt dubbele randen
    3. Exacte pixel positions - geen subpixel afronding
    """
    width, height = original_img.size
    new_width = width + (bleed_pixels * 2)
    new_height = height + (bleed_pixels * 2)
    
    if method == "Wit / Geselecteerde Kleur":
        # Eenvoudige kleurvulling - geen risico op haarlijnen
        color = custom_color if custom_color else (255, 255, 255)
        new_img = Image.new('RGB', (new_width, new_height), color)
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
    elif method == "Spiegelen (Mirror)":
        # FIX 1: Start met leeg canvas, GEEN resize!
        new_img = Image.new('RGB', (new_width, new_height))
        
        # Plak origineel in het midden
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        # FIX 2: Geen +1 overlap - exacte pixels
        # Spiegel bovenrand (exact bleed_pixels, niet +1)
        if bleed_pixels > 0:
            top_mirror = original_img.crop((0, 0, width, bleed_pixels))
            top_mirror = top_mirror.transpose(Image.FLIP_TOP_BOTTOM)
            new_img.paste(top_mirror, (bleed_pixels, 0))
            
            # Spiegel onderrand
            bottom_mirror = original_img.crop((0, height - bleed_pixels, width, height))
            bottom_mirror = bottom_mirror.transpose(Image.FLIP_TOP_BOTTOM)
            new_img.paste(bottom_mirror, (bleed_pixels, new_height - bleed_pixels))
            
            # Spiegel linkerrand
            left_mirror = original_img.crop((0, 0, bleed_pixels, height))
            left_mirror = left_mirror.transpose(Image.FLIP_LEFT_RIGHT)
            new_img.paste(left_mirror, (0, bleed_pixels))
            
            # Spiegel rechterrand
            right_mirror = original_img.crop((width - bleed_pixels, 0, width, height))
            right_mirror = right_mirror.transpose(Image.FLIP_LEFT_RIGHT)
            new_img.paste(right_mirror, (new_width - bleed_pixels, bleed_pixels))
            
            # Spiegel hoeken
            if bleed_pixels > 0:
                # Boven-links
                top_left = original_img.crop((0, 0, bleed_pixels, bleed_pixels))
                top_left = top_left.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
                new_img.paste(top_left, (0, 0))
                
                # Boven-rechts
                top_right = original_img.crop((width - bleed_pixels, 0, width, bleed_pixels))
                top_right = top_right.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
                new_img.paste(top_right, (new_width - bleed_pixels, 0))
                
                # Onder-links
                bottom_left = original_img.crop((0, height - bleed_pixels, bleed_pixels, height))
                bottom_left = bottom_left.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
                new_img.paste(bottom_left, (0, new_height - bleed_pixels))
                
                # Onder-rechts
                bottom_right = original_img.crop((width - bleed_pixels, height - bleed_pixels, width, height))
                bottom_right = bottom_right.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
                new_img.paste(bottom_right, (new_width - bleed_pixels, new_height - bleed_pixels))
        
    elif method == "Randpixels Uitrekken (Stretch)":
        # FIX: Start met leeg canvas
        new_img = Image.new('RGB', (new_width, new_height))
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        if bleed_pixels > 0:
            # Rek bovenrand uit (exacte pixels)
            top_strip = original_img.crop((0, 0, width, 1))
            top_stretched = top_strip.resize((width, bleed_pixels), Image.Resampling.NEAREST)
            new_img.paste(top_stretched, (bleed_pixels, 0))
            
            # Rek onderrand uit
            bottom_strip = original_img.crop((0, height-1, width, height))
            bottom_stretched = bottom_strip.resize((width, bleed_pixels), Image.Resampling.NEAREST)
            new_img.paste(bottom_stretched, (bleed_pixels, new_height - bleed_pixels))
            
            # Rek linkerrand uit
            left_strip = original_img.crop((0, 0, 1, height))
            left_stretched = left_strip.resize((bleed_pixels, height), Image.Resampling.NEAREST)
            new_img.paste(left_stretched, (0, bleed_pixels))
            
            # Rek rechterrand uit
            right_strip = original_img.crop((width-1, 0, width, height))
            right_stretched = right_strip.resize((bleed_pixels, height), Image.Resampling.NEAREST)
            new_img.paste(right_stretched, (new_width - bleed_pixels, bleed_pixels))
            
            # Vul hoeken
            corner_color = original_img.getpixel((0, 0))
            corner = Image.new('RGB', (bleed_pixels, bleed_pixels), corner_color)
            new_img.paste(corner, (0, 0))
            new_img.paste(corner, (new_width - bleed_pixels, 0))
            new_img.paste(corner, (0, new_height - bleed_pixels))
            new_img.paste(corner, (new_width - bleed_pixels, new_height - bleed_pixels))
        
    elif method == "Dominante Achtergrondkleur":
        dominant_color = get_dominant_color(original_img)
        new_img = Image.new('RGB', (new_width, new_height), dominant_color)
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
    
    return new_img

def export_to_pdf_haarlijnvrij(image, convert_cmyk, profile_name, output_format, bleed_mm):
    """
    EXPORTEER NAAR PDF ZONDER HAARLIJNEN
    Fixes:
    1. PNG ipv JPEG - geen compressie artifacts
    2. Overscan - overfill de pagina met 0.5pt
    3. Exacte positioning - geen subpixel afronding
    """
    # Bereken afmetingen in punten (1 pt = 1/72 inch)
    width_pt = (image.width / 300.0) * 72.0
    height_pt = (image.height / 300.0) * 72.0
    
    # FIX: Overscan van 0.5 punt om haarlijnen te voorkomen
    overscan = 0.5  # punt
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width_pt + overscan, height_pt + overscan))
    
    # Witte achtergrond
    c.setFillColorRGB(1, 1, 1)
    c.rect(0, 0, width_pt + overscan, height_pt + overscan, fill=1, stroke=0)
    
    # Metadata voor CMYK
    if convert_cmyk:
        c.setProducer(f"C.A. Bleed Tool - CMYK ({profile_name}) - Haarlijn Vrij")
        c.setTitle(f"C.A. Document - {output_format} - {bleed_mm}mm bleed")
    
    # FIX: Gebruik PNG ipv JPEG (geen compressie artifacts!)
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
        temp_path = tmp_file.name
        
        if convert_cmyk:
            # Converteer naar CMYK en bewaar als PNG
            cmyk_img = image.convert('CMYK')
            cmyk_img.save(temp_path, 'PNG', dpi=(300, 300))
        else:
            image.save(temp_path, 'PNG', dpi=(300, 300))
    
    # FIX: Plaats afbeelding met overscan (iets groter dan pagina)
    img_reader = ImageReader(temp_path)
    c.drawImage(
        img_reader,
        -overscan/2,  # Iets naar links/rechts overlappen
        -overscan/2,  # Iets naar boven/onder overlappen
        width=width_pt + overscan,
        height=height_pt + overscan,
        preserveAspectRatio=False
    )
    
    c.showPage()
    c.save()
    
    # Opruimen
    try:
        os.unlink(temp_path)
    except:
        pass
        
    return buffer.getvalue()

def check_aspect_ratio(image, format_name):
    """Controleer aspect ratio"""
    format_mm = FORMATS[format_name]
    target_ratio = format_mm[0] / format_mm[1]
    image_ratio = image.width / image.height
    ratio_diff = abs((image_ratio - target_ratio) / target_ratio) * 100
    
    if ratio_diff > 10:
        return f"⚠️ Aspect ratio verschil van {ratio_diff:.1f}% - beeld wordt bijgesneden"
    else:
        return f"✓ Aspect ratio ok ({ratio_diff:.1f}% verschil)"

# ============================================================================
# HOOFD INTERFACE
# ============================================================================

st.title("📐 C.A. Professional Bleed Tool - Haarlijn Vrij")
st.subheader("Professionele afloopruimte zonder zichtbare naden of snijranden")

with st.sidebar:
    st.header("🔧 Drukwerk Instellingen")
    
    selected_format = st.selectbox("📄 Doelformaat:", list(FORMATS.keys()), index=1)
    width_mm, height_mm = FORMATS[selected_format]
    st.caption(f"{width_mm} × {height_mm} mm")
    
    st.divider()
    
    # Bleed instellingen
    bleed_mm = st.number_input("📏 Bleed (mm):", min_value=0.0, max_value=20.0, value=3.0, step=0.5, format="%.1f")
    st.caption("Aanbevolen: 3mm voor drukwerk")
    
    fill_method = st.radio(
        "🎨 Vulmethode:",
        ["Spiegelen (Mirror)", "Randpixels Uitrekken (Stretch)", "Wit / Geselecteerde Kleur", "Dominante Achtergrondkleur"],
        help="Mirror: beste voor patronen | Stretch: beste voor foto's"
    )
    
    # Kleur selectie
    chosen_rgb = (255, 255, 255)
    if fill_method == "Wit / Geselecteerde Kleur":
        hex_color = st.color_picker("🎨 Randkleur:", "#FFFFFF")
        chosen_rgb = tuple(int(hex_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        c, m, y, k = rgb_to_cmyk(*chosen_rgb)
        st.caption(f"CMYK: {c:.0f}%, {m:.0f}%, {y:.0f}%, {k:.0f}%")
    
    st.divider()
    
    # CMYK instellingen
    st.subheader("🖨️ CMYK")
    convert_to_cmyk = st.checkbox("CMYK conversie", value=True)
    if convert_to_cmyk:
        color_profile = st.selectbox("Profiel:", list(COLOR_PROFILES.keys()), index=0)
        st.caption(COLOR_PROFILES[color_profile])
    
    st.divider()
    
    # Output
    output_type = st.radio("📁 Output:", ["PDF (Aanbevolen)", "PNG"])
    
    # PDF import
    st.divider()
    st.subheader("📑 PDF Import")
    crop_marks_remove = st.checkbox("Verwijder snijtekens", value=True)
    if crop_marks_remove:
        crop_pixels = st.slider("Wegknippen (pixels):", 20, 100, 35)

# Bestand upload
st.markdown("### 📂 1. Upload bestand")
uploaded_file = st.file_uploader(
    "PDF, JPG, JPEG of PNG",
    type=["jpg", "jpeg", "png", "pdf"]
)

if uploaded_file is not None:
    try:
        # Laad bestand
        file_bytes = uploaded_file.read()
        file_ext = uploaded_file.name.split('.')[-1].lower()
        
        with st.spinner("📄 Laden..."):
            if file_ext == 'pdf':
                if not PDF_IMPORT:
                    st.error("Installeer pdf2image: pip install pdf2image")
                    st.stop()
                
                images = convert_from_bytes(file_bytes, first_page=1, last_page=1, dpi=300)
                if images:
                    original_img = images[0]
                    if crop_marks_remove:
                        original_img = remove_crop_marks(original_img, crop_pixels)
                        st.success(f"✓ Snijtekens verwijderd")
                else:
                    st.error("Kan PDF niet laden")
                    st.stop()
            else:
                original_img = Image.open(io.BytesIO(file_bytes))
            
            if original_img.mode != 'RGB':
                original_img = original_img.convert('RGB')
        
        # Aspect ratio check
        st.markdown("### 📏 2. Formaat check")
        aspect_msg = check_aspect_ratio(original_img, selected_format)
        if "⚠️" in aspect_msg:
            st.warning(aspect_msg)
        else:
            st.success(aspect_msg)
        
        # Preview
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<p class="report-title">📸 Origineel</p>', unsafe_allow_html=True)
            st.image(original_img, use_container_width=True)
        
        # Verwerk bleed
        with st.spinner("🔧 Bleed toevoegen (haarlijnvrij)..."):
            # Resize naar exact formaat
            target_width = int(width_mm / 25.4 * 300)
            target_height = int(height_mm / 25.4 * 300)
            resized_img = original_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Bleed pixels
            bleed_pixels = int(bleed_mm / 25.4 * 300)
            
            # Creëer naadloze bleed
            final_img = create_seamless_bleed(resized_img, bleed_pixels, fill_method, chosen_rgb)
        
        with col2:
            st.markdown('<p class="report-title">✨ Met Bleed</p>', unsafe_allow_html=True)
            st.image(final_img, use_container_width=True)
            st.success(f"✅ +{bleed_mm}mm bleed (haarlijnvrij)")
        
        # Export
        st.markdown("### 💾 3. Exporteer")
        
        base_name = os.path.splitext(uploaded_file.name)[0]
        cmyk_suffix = "_CMYK" if convert_to_cmyk and output_type == "PDF (Aanbevolen)" else ""
        
        if output_type == "PDF (Aanbevolen)":
            if not PDF_SUPPORT:
                st.error("Installeer reportlab: pip install reportlab")
                st.stop()
            
            with st.spinner("📑 PDF genereren (haarlijnvrij)..."):
                pdf_data = export_to_pdf_haarlijnvrij(
                    final_img, convert_to_cmyk, color_profile, selected_format, bleed_mm
                )
                
                st.download_button(
                    label=f"📥 Download {selected_format} PDF {cmyk_suffix}",
                    data=pdf_data,
                    file_name=f"{base_name}{cmyk_suffix}_BLEED{int(bleed_mm)}mm_{selected_format}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                
                if convert_to_cmyk:
                    st.info(f"🖨️ CMYK Ready - {color_profile}")
        else:
            # PNG export
            buffer = io.BytesIO()
            final_img.save(buffer, format="PNG", dpi=(300, 300))
            
            st.download_button(
                label=f"📥 Download {selected_format} PNG",
                data=buffer.getvalue(),
                file_name=f"{base_name}{cmyk_suffix}_BLEED{int(bleed_mm)}mm_{selected_format}.png",
                mime="image/png",
                use_container_width=True
            )
        
        st.balloons()
        
    except Exception as e:
        st.error(f"Fout: {str(e)}")
        st.exception(e)

else:
    # Info
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📌 Stappen\n1. Upload bestand\n2. Kies formaat\n3. Stel bleed in\n4. Download")
    
    with col2:
        st.markdown("### 🎨 Methodes\n- Mirror: voor patronen\n- Stretch: voor foto's\n- Kleur: strak design\n- Dominant: automatisch")
    
    with col3:
        st.markdown("### ✨ Features\n- ✓ Geen haarlijnen\n- ✓ Geen JPEG artifacts\n- ✓ Overscan fix\n- ✓ PNG in PDF pipeline")

st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #666;'>© 2024 C.A. Professional Bleed Tool | Haarlijnvrij voor drukwerk</p>", 
    unsafe_allow_html=True
)
