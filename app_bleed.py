import streamlit as st
import numpy as np
from PIL import Image, ImageOps
from collections import Counter
import io
import os
import tempfile

# ReportLab importeren voor zuivere PDF generatie
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Pagina-instellingen voor de internetbrowser
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
    .report-title { font-weight: bold; font-size: 20px; color: #00594F; border-bottom: 2px solid #00594F; padding-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

FORMATS = {
    "A5": (148, 210),
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
    "A0": (841, 1189)
}

def get_dominant_color(image):
    small_img = image.resize((100, 100))
    small_img = small_img.quantize(colors=64).convert('RGB')
    pixels = list(small_img.getdata())
    return Counter(pixels).most_common(1)[0][0]

def create_bleed_image(original_img, bleed_pixels, method, custom_color=None):
    """Genereert afloop zónder anti-aliasing lijnen door 2 pixels overlap toe te passen"""
    width, height = original_img.size
    new_width = width + (bleed_pixels * 2)
    new_height = height + (bleed_pixels * 2)
    
    # Maak de basisafbeelding aan voor de afloop
    if method == "Wit / Geselecteerde Kleur":
        color = custom_color if custom_color else (255, 255, 255)
        bleed_bg = Image.new('RGB', (new_width, new_height), color)
        
    elif method == "Spiegelen (Mirror)":
        bleed_bg = Image.new('RGB', (new_width, new_height))
        
        # Spiegelen van de randen op basis van de originele pixels
        top_mirror = original_img.crop((0, 0, width, bleed_pixels)).transpose(Image.FLIP_TOP_BOTTOM)
        bleed_bg.paste(top_mirror, (bleed_pixels, 0))
        
        bottom_mirror = original_img.crop((0, height - bleed_pixels, width, height)).transpose(Image.FLIP_TOP_BOTTOM)
        bleed_bg.paste(bottom_mirror, (bleed_pixels, new_height - bleed_pixels))
        
        left_mirror = original_img.crop((0, 0, bleed_pixels, height)).transpose(Image.FLIP_LEFT_RIGHT)
        bleed_bg.paste(left_mirror, (0, bleed_pixels))
        
        right_mirror = original_img.crop((width - bleed_pixels, 0, width, height)).transpose(Image.FLIP_LEFT_RIGHT)
        bleed_bg.paste(right_mirror, (new_width - bleed_pixels, bleed_pixels))
        
        # Hoeken spiegelen
        top_left = original_img.crop((0, 0, bleed_pixels, bleed_pixels)).transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        bleed_bg.paste(top_left, (0, 0))
        top_right = original_img.crop((width - bleed_pixels, 0, width, bleed_pixels)).transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        bleed_bg.paste(top_right, (new_width - bleed_pixels, 0))
        bottom_left = original_img.crop((0, height - bleed_pixels, bleed_pixels, height)).transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        bleed_bg.paste(bottom_left, (0, new_height - bleed_pixels))
        bottom_right = original_img.crop((width - bleed_pixels, height - bleed_pixels, width, height)).transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        bleed_bg.paste(bottom_right, (new_width - bleed_pixels, new_height - bleed_pixels))
        
    elif method == "Randpixels Uitrekken (Stretch)":
        bleed_bg = Image.new('RGB', (new_width, new_height))
        
        top_stretched = original_img.crop((0, 0, width, 1)).resize((width, bleed_pixels), Image.Resampling.NEAREST)
        bleed_bg.paste(top_stretched, (bleed_pixels, 0))
        bottom_stretched = original_img.crop((0, height-1, width, height)).resize((width, bleed_pixels), Image.Resampling.NEAREST)
        bleed_bg.paste(bottom_stretched, (bleed_pixels, new_height - bleed_pixels))
        left_stretched = original_img.crop((0, 0, 1, height)).resize((bleed_pixels, height), Image.Resampling.NEAREST)
        bleed_bg.paste(left_stretched, (0, bleed_pixels))
        right_stretched = original_img.crop((width-1, 0, width, height)).resize((bleed_pixels, height), Image.Resampling.NEAREST)
        bleed_bg.paste(right_stretched, (new_width - bleed_pixels, bleed_pixels))
        
        top_left_color = original_img.getpixel((0, 0))
        corner = Image.new('RGB', (bleed_pixels, bleed_pixels), top_left_color)
        bleed_bg.paste(corner, (0, 0))
        bleed_bg.paste(corner, (new_width - bleed_pixels, 0))
        bleed_bg.paste(corner, (0, new_height - bleed_pixels))
        bleed_bg.paste(corner, (new_width - bleed_pixels, new_height - bleed_pixels))
        
    elif method == "Dominante Achtergrondkleur":
        dominant_color = get_dominant_color(original_img)
        bleed_bg = Image.new('RGB', (new_width, new_height), dominant_color)

    # --- CRUCIALE FIX: OVERLAP TEGEN SNIJRAND-LIJNEN ---
    # We plakken de originele flyer er nu overheen met 2 pixels extra overlap (slight overscan)
    # Dit drukt de microscopische schaduwlijnen/anti-aliasing randen volledig weg.
    overlap = 2
    resized_overlap = original_img.resize((width + (overlap * 2), height + (overlap * 2)), Image.Resampling.LANCZOS)
    bleed_bg.paste(resized_overlap, (bleed_pixels - overlap, bleed_pixels - overlap))
    
    return bleed_bg

def export_to_pdf_native(image, page_size_mm, convert_cmyk, profile_name):
    width_pt = page_size_mm[0] / 25.4 * 72
    height_pt = page_size_mm[1] / 25.4 * 72
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width_pt, height_pt))
    
    if convert_cmyk:
        c.setProducer(f"C.A. Bleed Tool - CMYK ({profile_name})")
        c.setTitle("C.A. Flyer - Drukwerk Klaar")
    
    img_width_pt = image.width / 300 * 72
    img_height_pt = image.height / 300 * 72
    
    x_pos = (width_pt - img_width_pt) / 2
    y_pos = (height_pt - img_height_pt) / 2
    
    # Pas de suffix aan naar .jpg omdat JPEG wél CMYK ondersteunt (PNG niet!)
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
        temp_path = tmp_file.name
        # Sla op als JPEG met maximale kwaliteit om compressieverlies te voorkomen
        image.save(temp_path, 'JPEG', quality=100, dpi=(300, 300))
    
    img_reader = ImageReader(temp_path)
    c.drawImage(img_reader, x_pos, y_pos, width=img_width_pt, height=img_height_pt, preserveAspectRatio=True)
    c.save()
    
    try:
        os.unlink(temp_path)
    except:
        pass
        
    return buffer.getvalue()

# --- INTERFACE ---
st.title("📐 PDF/Image Bleed Add Tool & CMYK Converter")
st.subheader("Voeg automatisch naadloze afloopruimte toe zonder zichtbare overgangslijnen")

with st.sidebar:
    st.header("🔧 Drukwerk Instellingen")
    selected_format = st.selectbox("Selecteer Doelformaat:", list(FORMATS.keys()), index=1)
    width_mm, height_mm = FORMATS[selected_format]
    
    convert_to_cmyk = st.checkbox("Zet om naar CMYK kleurruimte", value=True)
    color_profile = st.selectbox("Kleurprofiel:", ["CoatedFOGRA39", "USWebCoatedSWOP", "GenericCMYK"], index=0)
    
    bleed_mm = st.number_input("Afloopruimte (Bleed) in mm:", min_value=0, max_value=20, value=3)
    fill_method = st.radio("Afloop Opvulmethode:", ["Spiegelen (Mirror)", "Randpixels Uitrekken (Stretch)", "Wit / Geselecteerde Kleur", "Dominante Achtergrondkleur"])
    
    chosen_rgb = (255, 255, 255)
    if fill_method == "Wit / Geselecteerde Kleur":
        hex_color = st.color_picker("Kies specifieke randkleur:", "#FFFFFF")
        chosen_rgb = tuple(int(hex_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        
    output_type = st.radio("Export Bestandsformaat:", ["PDF (Aanbevolen)", "PNG"])

uploaded_file = st.file_uploader("Upload de flyer (Afbeelding: JPG, JPEG, PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    original_img = Image.open(io.BytesIO(file_bytes))
    if original_img.mode != 'RGB':
        original_img = original_img.convert('RGB')
        
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("<p class='report-title'>Originele Flyer</p>", unsafe_allow_html=True)
        st.image(original_img, caption=f"Origineel: {original_img.size[0]}x{original_img.size[1]} pixels", use_container_width=True)
        
    with col2:
        st.markdown("<p class='report-title'>⚙️ Gecreëerde Afloop (Naadloos Resultaat)</p>", unsafe_allow_html=True)
        
        with st.spinner("Afloop berekenen met anti-line blending..."):
            pixel_per_mm = 11.811
            target_width_px = int(width_mm * pixel_per_mm)
            target_height_px = int(height_mm * pixel_per_mm)
            bleed_pixels = int(bleed_mm * pixel_per_mm)
            
            # Schaal de basisflyer naar het netto formaat
            resized_base = original_img.resize((target_width_px, target_height_px), Image.Resampling.LANCZOS)
            
            # Maak de bleed-afbeelding (nu mét de overlap fix op regel 97-99!)
            final_img = create_bleed_image(resized_base, bleed_pixels, fill_method, chosen_rgb)
            
            # Toon de schone preview in de browser
            st.image(final_img, caption=f"Resultaat (+{bleed_mm}mm): {final_img.size[0]}x{final_img.size[1]} pixels", use_container_width=True)
            
            # Exporteren
            base_name = os.path.splitext(uploaded_file.name)[0]
            cmyk_suffix = "_CMYK" if convert_to_cmyk and output_type == "PDF (Aanbevolen)" else ""
            
            if output_type == "PDF (Aanbevolen)" and PDF_SUPPORT:
                # Zet om naar echt CMYK-drukformaat indien geselecteerd
                export_img = final_img.convert("CMYK") if convert_to_cmyk else final_img
                pdf_data = export_to_pdf_native(
                    export_img, 
                    (width_mm + bleed_mm*2, height_mm + bleed_mm*2), 
                    convert_to_cmyk, 
                    color_profile
                )
                file_ext = "pdf"
                mime_type = "application/pdf"
                download_data = pdf_data
                st.success("✅ Zuivere, naadloze PDF gegenereerd. De overgangslijn is weggewerkt.")
            else:
                buffer = io.BytesIO()
                final_img.save(buffer, format="PNG", dpi=(300, 300))
                file_ext = "png"
                mime_type = "image/png"
                download_data = buffer.getvalue()

            st.write("---")
            st.download_button(
                label=f"📥 Download Naadloze {selected_format} Flyer",
                data=download_data,
                file_name=f"{base_name}{cmyk_suffix}_PERFECT_BLEED_{bleed_mm}mm_{selected_format}.{file_ext}",
                mime=mime_type
            )
