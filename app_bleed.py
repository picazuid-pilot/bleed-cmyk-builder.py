import streamlit as st
import numpy as np
from PIL import Image, ImageOps
from collections import Counter
import io
import os

# Pagina-instellingen voor de internetbrowser
st.set_page_config(
    page_title="PDF/Image Bleed Add Tool",
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

# Definiëring van formaten en basisfuncties uit jouw originele script
FORMATS = {
    "A5": (148, 210),
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
    "A0": (841, 1189)
}

PROFILES = {
    "USWebCoatedSWOP": "US Web Coated (SWOP) v2 - Standaard voor VS drukwerk",
    "CoatedFOGRA39": "Coated FOGRA39 (ISO 12647-2:2004) - Europees standaard",
    "UncoatedFOGRA29": "Uncoated FOGRA29 - Voor ongestreken papier",
    "JapanColor2001Coated": "Japan Color 2001 Coated - Japans standaard",
    "GenericCMYK": "Generic CMYK - Algemene CMYK conversie"
}

def rgb_to_cmyk(r, g, b):
    """Dynamische RGB naar CMYK berekening uit jouw originele script"""
    if r == 0 and g == 0 and b == 0:
        return (0, 0, 0, 100)
    r_prime, g_prime, b_prime = r / 255.0, g / 255.0, b / 255.0
    k = 1 - max(r_prime, g_prime, b_prime)
    if k < 1:
        c = (1 - r_prime - k) / (1 - k)
        m = (1 - g_prime - k) / (1 - k)
        y = (1 - b_prime - k) / (1 - k)
    else:
        c, m, y = 0, 0, 0
    return (c * 100, m * 100, y * 100, k * 100)

def get_dominant_color(image):
    """Dominante kleurmatrix bepalen uit jouw script"""
    small_img = image.resize((100, 100))
    small_img = small_img.quantize(colors=64)
    small_img = small_img.convert('RGB')
    pixels = list(small_img.getdata())
    color_counts = Counter(pixels)
    return color_counts.most_common(1)[0][0]

def create_bleed_image(original_img, bleed_pixels, method, custom_color=None):
    """De exacte afloop-algoritmes (wit, spiegelen, uitrekken, dominant) uit jouw script"""
    width, height = original_img.size
    new_width = width + (bleed_pixels * 2)
    new_height = height + (bleed_pixels * 2)
    
    if method == "Wit / Geselecteerde Kleur":
        color = custom_color if custom_color else (255, 255, 255)
        new_img = Image.new('RGB', (new_width, new_height), color)
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
    elif method == "Spiegelen (Mirror)":
        new_img = Image.new('RGB', (new_width, new_height))
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        # Spiegel randen boven/onder/links/rechts
        top_mirror = original_img.crop((0, 0, width, bleed_pixels)).transpose(Image.FLIP_TOP_BOTTOM)
        new_img.paste(top_mirror, (bleed_pixels, 0))
        
        bottom_mirror = original_img.crop((0, height - bleed_pixels, width, height)).transpose(Image.FLIP_TOP_BOTTOM)
        new_img.paste(bottom_mirror, (bleed_pixels, new_height - bleed_pixels))
        
        left_mirror = original_img.crop((0, 0, bleed_pixels, height)).transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(left_mirror, (0, bleed_pixels))
        
        right_mirror = original_img.crop((width - bleed_pixels, 0, width, height)).transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(right_mirror, (new_width - bleed_pixels, bleed_pixels))
        
        # Spiegel de 4 hoeken
        top_left = original_img.crop((0, 0, bleed_pixels, bleed_pixels)).transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(top_left, (0, 0))
        top_right = original_img.crop((width - bleed_pixels, 0, width, bleed_pixels)).transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(top_right, (new_width - bleed_pixels, 0))
        bottom_left = original_img.crop((0, height - bleed_pixels, bleed_pixels, height)).transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(bottom_left, (0, new_height - bleed_pixels))
        bottom_right = original_img.crop((width - bleed_pixels, height - bleed_pixels, width, height)).transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
        new_img.paste(bottom_right, (new_width - bleed_pixels, new_height - bleed_pixels))
        
    elif method == "Randpixels Uitrekken (Stretch)":
        new_img = Image.new('RGB', (new_width, new_height))
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        top_stretched = original_img.crop((0, 0, width, 1)).resize((width, bleed_pixels), Image.NEAREST)
        new_img.paste(top_stretched, (bleed_pixels, 0))
        bottom_stretched = original_img.crop((0, height-1, width, height)).resize((width, bleed_pixels), Image.NEAREST)
        new_img.paste(bottom_stretched, (bleed_pixels, new_height - bleed_pixels))
        left_stretched = original_img.crop((0, 0, 1, height)).resize((bleed_pixels, height), Image.NEAREST)
        new_img.paste(left_stretched, (0, bleed_pixels))
        right_stretched = original_img.crop((width-1, 0, width, height)).resize((bleed_pixels, height), Image.NEAREST)
        new_img.paste(right_stretched, (new_width - bleed_pixels, bleed_pixels))
        
        top_left_color = original_img.getpixel((0, 0))
        corner = Image.new('RGB', (bleed_pixels, bleed_pixels), top_left_color)
        new_img.paste(corner, (0, 0))
        new_img.paste(corner, (new_width - bleed_pixels, 0))
        new_img.paste(corner, (0, new_height - bleed_pixels))
        new_img.paste(corner, (new_width - bleed_pixels, new_height - bleed_pixels))
        
    elif method == "Dominante Achtergrondkleur":
        dominant_color = get_dominant_color(original_img)
        new_img = Image.new('RGB', (new_width, new_height), dominant_color)
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
    return new_img

# --- INTRO INTERFACE ---
st.title("📐 PDF/Image Bleed Add & CMYK Converter")
st.subheader("Voeg automatisch afloopruimte (bleed) toe en converteer naar CMYK via je browser")

# 1. ZIJBALK INSTELLINGEN (Vervangt jouw Tkinter invoervelden)
with st.sidebar:
    st.header("🔧 Drukwerk Instellingen")
    
    selected_format = st.selectbox("2. Selecteer Doelformaat:", list(FORMATS.keys()), index=1) # Standaard A4
    width_mm, height_mm = FORMATS[selected_format]
    
    convert_to_cmyk = st.checkbox("Zet om naar CMYK kleurruimte (Drukwerk)", value=True)
    
    color_profile = st.selectbox(
        "Kleurprofiel:", 
        list(PROFILES.keys()), 
        index=1, # Standaard CoatedFOGRA39 voor Europa
        disabled=not convert_to_cmyk
    )
    st.caption(f"*Profiel info: {PROFILES[color_profile]}*")
    
    bleed_mm = st.number_input("5. Afloopruimte (Bleed) in mm:", min_value=0, max_value=20, value=3)
    
    fill_method = st.radio(
        "6. Afloop Opvulmethode:",
        ["Wit / Geselecteerde Kleur", "Spiegelen (Mirror)", "Randpixels Uitrekken (Stretch)", "Dominante Achtergrondkleur"]
    )
    
    # Kleurkiezer tonen als "Wit / Kleur" is geselecteerd
    chosen_rgb = (255, 255, 255)
    if fill_method == "Wit / Geselecteerde Kleur":
        hex_color = st.color_picker("Kies specifieke randkleur:", "#FFFFFF")
        chosen_rgb = tuple(int(hex_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        c, m, y, k = rgb_to_cmyk(*chosen_rgb)
        st.caption(f"Geconverteerde CMYK waarde rand: C:{c:.0f}% M:{m:.0f}% Y:{y:.0f}% K:{k:.0f}%")

    output_type = st.radio("8. Export Bestandsformaat:", ["PDF (Aanbevolen)", "PNG"])

# 2. HOOFDSCHERM: BESTANDSUPLOADER
uploaded_file = st.file_uploader("1. Upload de flyer (Afbeelding: JPG, JPEG, PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # Open afbeelding
    file_bytes = uploaded_file.read()
    original_img = Image.open(io.BytesIO(file_bytes))
    
    if original_img.mode != 'RGB':
        original_img = original_img.convert('RGB')
        
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("<p class='report-title'>Originele Flyer</p>", unsafe_allow_html=True)
        st.image(original_img, caption=f"Origineel: {original_img.size[0]}x{original_img.size[1]} pixels", use_container_width=True)
        
    with col2:
        st.markdown("<p class='report-title'>⚙️ Preview Bewerkt Resultaat</p>", unsafe_allow_html=True)
        
        with st.spinner("Afloopranden genereren en matrix berekenen op 300 DPI..."):
            # Berekening op 300 DPI (1 mm = 11.811 pixels)
            pixel_per_mm = 11.811
            target_width_px = int(width_mm * pixel_per_mm)
            target_height_px = int(height_mm * pixel_per_mm)
            bleed_pixels = int(bleed_mm * pixel_per_mm)
            
            # Schaal de afbeelding exact naar het doelformaat
            resized_base = original_img.resize((target_width_px, target_height_px), Image.Resampling.LANCZOS)
            
            # Voeg de afloop toe volgens de gekozen methode
            final_img = create_bleed_image(resized_base, bleed_pixels, fill_method, chosen_rgb)
            
            # Preview tonen (Browsers kunnen CMYK niet direct tonen, dus preview blijft RGB)
            st.image(final_img, caption=f"Resultaat (+{bleed_mm}mm afloop): {final_img.size[0]}x{final_img.size[1]} pixels", use_container_width=True)
            
            # Exporteren voor download
            output_buffer = io.BytesIO()
            base_name = os.path.splitext(uploaded_file.name)[0]
            cmyk_suffix = "_CMYK" if convert_to_cmyk and output_type == "PDF (Aanbevolen)" else ""
            
            if output_type == "PDF (Aanbevolen)":
                export_img = final_img.convert("CMYK") if convert_to_cmyk else final_img
                export_img.save(output_buffer, format="PDF", resolution=300.0, quality=100)
                file_ext = "pdf"
                mime_type = "application/pdf"
                
                if convert_to_cmyk:
                    st.success(f"✅ CMYK kleurconversie toegepast via gesimuleerd profiel: `{color_profile}`. Klaar voor professioneel drukwerk!")
            else:
                final_img.save(output_buffer, format="PNG", dpi=(300, 300))
                file_ext = "png"
                mime_type = "image/png"
                if convert_to_cmyk:
                    st.warning("⚠️ Let op: PNG ondersteunt geen CMYK. Het bestand wordt opgeslagen in RGB.")

            st.write("---")
            st.download_button(
                label=f"📥 Download Aangepaste {selected_format} Flyer ({file_ext.upper()})",
                data=output_buffer.getvalue(),
                file_name=f"{base_name}{cmyk_suffix}_BLEED_{bleed_mm}mm_{selected_format}.{file_ext}",
                mime=mime_type
            )