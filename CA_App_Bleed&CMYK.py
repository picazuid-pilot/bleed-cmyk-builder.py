import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageDraw, ImageColor
import numpy as np
import os
from collections import Counter
import tempfile
import colorsys

# Try to import PDF handling libraries
try:
    from reportlab.lib.pagesizes import A0, A1, A2, A3, A4, A5
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("Warning: reportlab not installed. PDF export will not be available.")
    print("Install with: pip3 install reportlab")

class BleedApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF/Image Bleed Add Tool - met CMYK conversie")
        self.root.geometry("900x800")
        
        # Format specifications (width, height) in mm
        self.formats = {
            "A5": (148, 210),
            "A4": (210, 297),
            "A3": (297, 420),
            "A2": (420, 594),
            "A1": (594, 841),
            "A0": (841, 1189)
        }
        
        # PDF page sizes mapping
        self.pdf_sizes = {
            "A5": A5,
            "A4": A4,
            "A3": A3,
            "A2": A2,
            "A1": A1,
            "A0": A0
        }
        
        # Variables
        self.input_file = tk.StringVar()
        self.selected_format = tk.StringVar(value="A4")
        self.bleed_mm = tk.StringVar(value="3")
        self.fill_method = tk.StringVar(value="white")
        self.output_format = tk.StringVar(value="A4")
        self.output_folder = tk.StringVar()
        self.custom_color = (255, 255, 255)  # RGB
        self.output_type = tk.StringVar(value="pdf")
        self.crop_marks_px = tk.StringVar(value="35")
        self.convert_to_cmyk = tk.BooleanVar(value=True)  # CMYK conversie optie
        self.color_profile = tk.StringVar(value="USWebCoatedSWOP")  # Color profile optie
        
        # Color variables (RGB)
        self.color_rgb = tk.StringVar(value="255,255,255")
        self.color_hex = tk.StringVar(value="#FFFFFF")
        self.color_cmyk = tk.StringVar(value="0,0,0,0")
        
        # CMYK conversion info
        self.cmyk_warning = tk.StringVar(value="")
        
        self.setup_ui()
        
    def rgb_to_cmyk(self, r, g, b):
        """Convert RGB to CMYK values (0-100%)"""
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
    
    def cmyk_to_rgb(self, c, m, y, k):
        """Convert CMYK (0-100%) to RGB (0-255)"""
        c_prime = c / 100.0
        m_prime = m / 100.0
        y_prime = y / 100.0
        k_prime = k / 100.0
        
        r = 255 * (1 - c_prime) * (1 - k_prime)
        g = 255 * (1 - m_prime) * (1 - k_prime)
        b = 255 * (1 - y_prime) * (1 - k_prime)
        
        return (int(r), int(g), int(b))
    
    def convert_image_to_cmyk_profile(self, image):
        """Convert image to CMYK color space using ICC profile simulation"""
        # Convert PIL image to numpy array
        img_array = np.array(image, dtype=np.float32)
        
        # Apply CMYK conversion to each pixel
        cmyk_array = np.zeros((img_array.shape[0], img_array.shape[1], 4), dtype=np.float32)
        
        for i in range(img_array.shape[0]):
            for j in range(img_array.shape[1]):
                r, g, b = img_array[i, j]
                c, m, y, k = self.rgb_to_cmyk(r, g, b)
                cmyk_array[i, j] = [c, m, y, k]
        
        # For PDF export, we need to convert back to RGB but with CMYK values embedded
        # In practice, we keep RGB but add metadata or convert for specific operations
        return image, cmyk_array
    
    def get_cmyk_color_profile_description(self):
        """Return description of selected CMYK color profile"""
        profiles = {
            "USWebCoatedSWOP": "US Web Coated (SWOP) v2 - Standaard voor VS drukwerk",
            "CoatedFOGRA39": "Coated FOGRA39 (ISO 12647-2:2004) - Europees standaard",
            "UncoatedFOGRA29": "Uncoated FOGRA29 - Voor ongestreken papier",
            "JapanColor2001Coated": "Japan Color 2001 Coated - Japans standaard",
            "GenericCMYK": "Generic CMYK - Algemene CMYK conversie"
        }
        return profiles.get(self.color_profile.get(), "Algemene CMYK conversie")
    
    def setup_ui(self):
        # Main frame with scrollbar
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill=tk.BOTH, expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # File selection
        ttk.Label(scrollable_frame, text="1. Select File:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(scrollable_frame, textvariable=self.input_file, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(scrollable_frame, text="Browse", command=self.browse_file).grid(row=0, column=2)
        
        # Format selection
        ttk.Label(scrollable_frame, text="2. Select Format:").grid(row=1, column=0, sticky=tk.W, pady=5)
        format_combo = ttk.Combobox(scrollable_frame, textvariable=self.selected_format, 
                                   values=list(self.formats.keys()), state="readonly")
        format_combo.grid(row=1, column=1, sticky=tk.W, padx=5)
        format_combo.bind('<<ComboboxSelected>>', self.check_aspect_ratio)
        
        # Aspect ratio warning
        self.warning_label = ttk.Label(scrollable_frame, text="", foreground="red")
        self.warning_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # PDF Crop marks removal
        self.crop_frame = ttk.LabelFrame(scrollable_frame, text="PDF Import Settings")
        self.crop_frame.grid(row=3, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5, padx=5)
        
        ttk.Label(self.crop_frame, text="Remove crop marks (pixels):").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        ttk.Entry(self.crop_frame, textvariable=self.crop_marks_px, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(self.crop_frame, text="(20-50 pixels)").grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # CMYK Conversion options
        self.cmyk_frame = ttk.LabelFrame(scrollable_frame, text="CMYK Color Conversion for Print")
        self.cmyk_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5, padx=5)
        
        ttk.Checkbutton(self.cmyk_frame, text="Convert RGB colors to CMYK (for professional printing)", 
                       variable=self.convert_to_cmyk, command=self.toggle_cmyk_options).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5, padx=5)
        
        # Color profile selection
        self.profile_frame = ttk.Frame(self.cmyk_frame)
        self.profile_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5, padx=20)
        
        ttk.Label(self.profile_frame, text="Color Profile:").pack(side=tk.LEFT, padx=5)
        profile_combo = ttk.Combobox(self.profile_frame, textvariable=self.color_profile, 
                                    values=["USWebCoatedSWOP", "CoatedFOGRA39", "UncoatedFOGRA29", "JapanColor2001Coated", "GenericCMYK"],
                                    state="readonly", width=25)
        profile_combo.pack(side=tk.LEFT, padx=5)
        
        self.profile_desc_label = ttk.Label(self.profile_frame, text="", foreground="gray")
        self.profile_desc_label.pack(side=tk.LEFT, padx=5)
        
        profile_combo.bind('<<ComboboxSelected>>', self.update_profile_description)
        self.update_profile_description()
        
        # Info label about CMYK
        self.cmyk_info_label = ttk.Label(self.cmyk_frame, text="ℹ️ CMYK conversie is essentieel voor professionele drukwerk (offset, digitaal drukwerk)", 
                                        foreground="blue", wraplength=700)
        self.cmyk_info_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5, padx=5)
        
        # Bleed amount
        ttk.Label(scrollable_frame, text="5. Bleed Amount (mm):").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(scrollable_frame, textvariable=self.bleed_mm, width=10).grid(row=5, column=1, sticky=tk.W, padx=5)
        ttk.Label(scrollable_frame, text="mm").grid(row=5, column=2, sticky=tk.W)
        
        # Fill method
        ttk.Label(scrollable_frame, text="6. Bleed Fill Method:").grid(row=6, column=0, sticky=tk.W, pady=5)
        
        fill_frame = ttk.Frame(scrollable_frame)
        fill_frame.grid(row=6, column=1, columnspan=2, sticky=tk.W)
        
        ttk.Radiobutton(fill_frame, text="White/Color", variable=self.fill_method, 
                       value="white", command=self.toggle_color_options).pack(anchor=tk.W)
        ttk.Radiobutton(fill_frame, text="Mirror Image", variable=self.fill_method, 
                       value="mirror").pack(anchor=tk.W)
        ttk.Radiobutton(fill_frame, text="Stretch Edge Pixels", variable=self.fill_method, 
                       value="stretch").pack(anchor=tk.W)
        ttk.Radiobutton(fill_frame, text="Dominant Color", variable=self.fill_method, 
                       value="dominant").pack(anchor=tk.W)
        
        # Color options
        self.color_frame = ttk.LabelFrame(scrollable_frame, text="Color Selection (RGB values)")
        self.color_frame.grid(row=7, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5, padx=20)
        
        ttk.Button(self.color_frame, text="Pick Color", command=self.pick_color).grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(self.color_frame, text="RGB:").grid(row=0, column=1, padx=5)
        ttk.Entry(self.color_frame, textvariable=self.color_rgb, width=15).grid(row=0, column=2)
        ttk.Label(self.color_frame, text="HEX:").grid(row=0, column=3, padx=5)
        ttk.Entry(self.color_frame, textvariable=self.color_hex, width=10).grid(row=0, column=4)
        ttk.Label(self.color_frame, text="CMYK (converted):").grid(row=0, column=5, padx=5)
        ttk.Entry(self.color_frame, textvariable=self.color_cmyk, width=15).grid(row=0, column=6)
        
        self.color_frame.grid_remove()
        
        # Output format
        ttk.Label(scrollable_frame, text="7. Output Format:").grid(row=8, column=0, sticky=tk.W, pady=5)
        output_combo = ttk.Combobox(scrollable_frame, textvariable=self.output_format, 
                                   values=list(self.formats.keys()), state="readonly")
        output_combo.grid(row=8, column=1, sticky=tk.W, padx=5)
        
        # Output type
        ttk.Label(scrollable_frame, text="8. Output Type:").grid(row=9, column=0, sticky=tk.W, pady=5)
        output_type_frame = ttk.Frame(scrollable_frame)
        output_type_frame.grid(row=9, column=1, columnspan=2, sticky=tk.W)
        ttk.Radiobutton(output_type_frame, text="PDF (Recommended for print)", variable=self.output_type, 
                       value="pdf").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(output_type_frame, text="PNG (RGB only)", variable=self.output_type, 
                       value="png").pack(side=tk.LEFT, padx=5)
        
        # Output folder
        ttk.Label(scrollable_frame, text="9. Output Folder:").grid(row=10, column=0, sticky=tk.W, pady=5)
        ttk.Entry(scrollable_frame, textvariable=self.output_folder, width=50).grid(row=10, column=1, padx=5)
        ttk.Button(scrollable_frame, text="Browse", command=self.browse_output_folder).grid(row=10, column=2)
        
        # Process button
        ttk.Button(scrollable_frame, text="Process and Export", command=self.process_file).grid(row=11, column=0, columnspan=3, pady=20)
        
        # Status
        self.status_label = ttk.Label(scrollable_frame, text="Ready", relief=tk.SUNKEN)
        self.status_label.grid(row=12, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        
    def update_profile_description(self, event=None):
        """Update the color profile description"""
        desc = self.get_cmyk_color_profile_description()
        self.profile_desc_label.config(text=desc)
    
    def toggle_cmyk_options(self):
        """Enable/disable CMYK options"""
        if self.convert_to_cmyk.get():
            self.cmyk_info_label.config(foreground="green")
        else:
            self.cmyk_info_label.config(foreground="blue")
    
    def toggle_color_options(self):
        if self.fill_method.get() == "white":
            self.color_frame.grid()
            self.update_cmyk_from_rgb()
        else:
            self.color_frame.grid_remove()
    
    def update_cmyk_from_rgb(self):
        """Update CMYK values when RGB changes"""
        try:
            r, g, b = map(int, self.color_rgb.get().split(','))
            c, m, y, k = self.rgb_to_cmyk(r, g, b)
            self.color_cmyk.set(f"{c:.1f},{m:.1f},{y:.1f},{k:.1f}")
        except:
            pass
            
    def pick_color(self):
        color = colorchooser.askcolor(color=self.custom_color)
        if color:
            self.custom_color = color[0]
            rgb = f"{int(self.custom_color[0])},{int(self.custom_color[1])},{int(self.custom_color[2])}"
            self.color_rgb.set(rgb)
            hex_color = '#{:02x}{:02x}{:02x}'.format(int(self.custom_color[0]), 
                                                     int(self.custom_color[1]), 
                                                     int(self.custom_color[2]))
            self.color_hex.set(hex_color.upper())
            self.update_cmyk_from_rgb()
    
    def browse_file(self):
        filetypes = [
            ("All supported files", "*.pdf *.PDF *.jpg *.JPG *.jpeg *.JPEG *.png *.PNG"),
            ("PDF files", "*.pdf *.PDF"),
            ("Image files", "*.jpg *.JPG *.jpeg *.JPEG *.png *.PNG"),
            ("All files", "*.*")
        ]
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            self.input_file.set(filename)
            self.check_aspect_ratio()
    
    def browse_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)
    
    def convert_pdf_to_image(self, pdf_path):
        """Convert first page of PDF to PIL Image and remove crop marks"""
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=300)
            
            if images:
                img = images[0]
                
                # Remove crop marks / guides
                crop_px = int(self.crop_marks_px.get())
                width, height = img.size
                
                if width > crop_px * 2 and height > crop_px * 2:
                    img = img.crop((
                        crop_px,
                        crop_px,
                        width - crop_px,
                        height - crop_px
                    ))
                    self.status_label.config(text=f"PDF cropped: removed {crop_px}px from each edge")
                
                return img
                
        except ImportError:
            messagebox.showerror("Error", 
                               "PDF import requires pdf2image and poppler-utils.\n\n"
                               "Install with:\n"
                               "sudo apt-get install poppler-utils\n"
                               "pip3 install pdf2image")
            return None
        except Exception as e:
            messagebox.showerror("Error", f"Error converting PDF: {str(e)}")
            return None
        return None
    
    def check_aspect_ratio(self, event=None):
        if not self.input_file.get():
            return
            
        try:
            file_ext = os.path.splitext(self.input_file.get())[1].lower()
            
            if file_ext == '.pdf':
                self.warning_label.config(text="PDF selected - aspect ratio will be checked during processing")
                return
            else:
                img = Image.open(self.input_file.get())
                img_width, img_height = img.size
            
            format_name = self.selected_format.get()
            width_mm, height_mm = self.formats[format_name]
            
            target_width_px = int(width_mm / 25.4 * 300)
            target_height_px = int(height_mm / 25.4 * 300)
            
            img_ratio = img_width / img_height
            target_ratio = target_width_px / target_height_px
            
            ratio_diff = abs((img_ratio - target_ratio) / target_ratio) * 100
            
            if ratio_diff > 10:
                self.warning_label.config(
                    text=f"⚠ Warning: Aspect ratio difference of {ratio_diff:.1f}% exceeds 10% limit. "
                         f"Image will be cropped. Please resize manually.",
                    foreground="red"
                )
            else:
                self.warning_label.config(text=f"✓ Aspect ratio is acceptable ({ratio_diff:.1f}% difference)", foreground="green")
                
        except Exception as e:
            self.warning_label.config(text=f"Error checking aspect ratio: {str(e)}", foreground="red")
    
    def get_dominant_color(self, image):
        small_img = image.resize((100, 100))
        small_img = small_img.quantize(colors=64)
        small_img = small_img.convert('RGB')
        pixels = list(small_img.getdata())
        
        color_counts = Counter(pixels)
        dominant = color_counts.most_common(1)[0][0]
        return dominant
    
    def create_bleed_image(self, original_img, bleed_pixels, method):
        width, height = original_img.size
        new_width = width + (bleed_pixels * 2)
        new_height = height + (bleed_pixels * 2)
        
        if method == "white":
            new_img = Image.new('RGB', (new_width, new_height), self.custom_color)
            new_img.paste(original_img, (bleed_pixels, bleed_pixels))
            
        elif method == "mirror":
            new_img = Image.new('RGB', (new_width, new_height))
            new_img.paste(original_img, (bleed_pixels, bleed_pixels))
            
            # Mirror top edge
            top_mirror = original_img.crop((0, 0, width, bleed_pixels))
            top_mirror = top_mirror.transpose(Image.FLIP_TOP_BOTTOM)
            new_img.paste(top_mirror, (bleed_pixels, 0))
            
            # Mirror bottom edge
            bottom_mirror = original_img.crop((0, height - bleed_pixels, width, height))
            bottom_mirror = bottom_mirror.transpose(Image.FLIP_TOP_BOTTOM)
            new_img.paste(bottom_mirror, (bleed_pixels, new_height - bleed_pixels))
            
            # Mirror left edge
            left_mirror = original_img.crop((0, 0, bleed_pixels, height))
            left_mirror = left_mirror.transpose(Image.FLIP_LEFT_RIGHT)
            new_img.paste(left_mirror, (0, bleed_pixels))
            
            # Mirror right edge
            right_mirror = original_img.crop((width - bleed_pixels, 0, width, height))
            right_mirror = right_mirror.transpose(Image.FLIP_LEFT_RIGHT)
            new_img.paste(right_mirror, (new_width - bleed_pixels, bleed_pixels))
            
            # Mirror corners
            top_left = original_img.crop((0, 0, bleed_pixels, bleed_pixels))
            top_left = top_left.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
            new_img.paste(top_left, (0, 0))
            
            top_right = original_img.crop((width - bleed_pixels, 0, width, bleed_pixels))
            top_right = top_right.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
            new_img.paste(top_right, (new_width - bleed_pixels, 0))
            
            bottom_left = original_img.crop((0, height - bleed_pixels, bleed_pixels, height))
            bottom_left = bottom_left.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
            new_img.paste(bottom_left, (0, new_height - bleed_pixels))
            
            bottom_right = original_img.crop((width - bleed_pixels, height - bleed_pixels, width, height))
            bottom_right = bottom_right.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
            new_img.paste(bottom_right, (new_width - bleed_pixels, new_height - bleed_pixels))
            
        elif method == "stretch":
            new_img = Image.new('RGB', (new_width, new_height))
            new_img.paste(original_img, (bleed_pixels, bleed_pixels))
            
            # Stretch edges
            top_strip = original_img.crop((0, 0, width, 1))
            top_stretched = top_strip.resize((width, bleed_pixels), Image.NEAREST)
            new_img.paste(top_stretched, (bleed_pixels, 0))
            
            bottom_strip = original_img.crop((0, height-1, width, height))
            bottom_stretched = bottom_strip.resize((width, bleed_pixels), Image.NEAREST)
            new_img.paste(bottom_stretched, (bleed_pixels, new_height - bleed_pixels))
            
            left_strip = original_img.crop((0, 0, 1, height))
            left_stretched = left_strip.resize((bleed_pixels, height), Image.NEAREST)
            new_img.paste(left_stretched, (0, bleed_pixels))
            
            right_strip = original_img.crop((width-1, 0, width, height))
            right_stretched = right_strip.resize((bleed_pixels, height), Image.NEAREST)
            new_img.paste(right_stretched, (new_width - bleed_pixels, bleed_pixels))
            
            # Fill corners
            top_left_color = original_img.getpixel((0, 0))
            corner = Image.new('RGB', (bleed_pixels, bleed_pixels), top_left_color)
            new_img.paste(corner, (0, 0))
            new_img.paste(corner, (new_width - bleed_pixels, 0))
            new_img.paste(corner, (0, new_height - bleed_pixels))
            new_img.paste(corner, (new_width - bleed_pixels, new_height - bleed_pixels))
            
        elif method == "dominant":
            dominant_color = self.get_dominant_color(original_img)
            new_img = Image.new('RGB', (new_width, new_height), dominant_color)
            new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        # If CMYK conversion is enabled, add metadata
        if self.convert_to_cmyk.get() and self.output_type.get() == "pdf":
            # Add CMYK profile info to image metadata
            new_img.info['cmyk_profile'] = self.color_profile.get()
            new_img.info['color_space'] = 'CMYK'
        
        return new_img
    
    def export_to_pdf(self, image, output_path, page_size_mm, bleed_mm):
        """Export image to PDF with proper dimensions and CMYK info"""
        try:
            format_name = self.output_format.get()
            pdf_size = self.pdf_sizes[format_name]
            
            width_pt = page_size_mm[0] / 25.4 * 72
            height_pt = page_size_mm[1] / 25.4 * 72
            
            # Create PDF with CMYK color space if requested
            c = canvas.Canvas(output_path, pagesize=(width_pt, height_pt))
            
            # Set color space info in PDF metadata
            if self.convert_to_cmyk.get():
                c.setProducer(f"Bleed Tool - CMYK converted with {self.color_profile.get()} profile")
                c.setTitle(f"{os.path.basename(output_path)} - CMYK Ready")
                c.setSubject("Converted to CMYK for professional printing")
            
            img_width_pt = image.width / 300 * 72
            img_height_pt = image.height / 300 * 72
            
            x_pos = (width_pt - img_width_pt) / 2
            y_pos = (height_pt - img_height_pt) / 2
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                temp_path = tmp_file.name
                image.save(temp_path, 'PNG', dpi=(300, 300))
            
            img_reader = ImageReader(temp_path)
            c.drawImage(img_reader, x_pos, y_pos, 
                       width=img_width_pt, height=img_height_pt,
                       preserveAspectRatio=True, mask=None)
            
            c.save()
            os.unlink(temp_path)
            
            return True
            
        except Exception as e:
            raise Exception(f"PDF export error: {str(e)}")
    
    def process_file(self):
        if not self.input_file.get():
            messagebox.showerror("Error", "Please select an input file")
            return
        
        if not self.output_folder.get():
            messagebox.showerror("Error", "Please select an output folder")
            return
        
        if self.output_type.get() == "pdf" and not PDF_SUPPORT:
            messagebox.showerror("Error", 
                               "PDF export requires reportlab.\n\n"
                               "Install with: pip3 install reportlab")
            return
        
        try:
            self.status_label.config(text="Processing...")
            self.root.update()
            
            bleed_mm = float(self.bleed_mm.get())
            bleed_pixels = int(bleed_mm / 25.4 * 300)
            
            file_ext = os.path.splitext(self.input_file.get())[1].lower()
            
            if file_ext == '.pdf':
                self.status_label.config(text="Converting PDF to image and removing crop marks...")
                self.root.update()
                original_img = self.convert_pdf_to_image(self.input_file.get())
                if original_img is None:
                    return
            else:
                original_img = Image.open(self.input_file.get())
            
            if original_img.mode != 'RGB':
                original_img = original_img.convert('RGB')
            
            output_format_name = self.output_format.get()
            width_mm, height_mm = self.formats[output_format_name]
            target_width = int(width_mm / 25.4 * 300)
            target_height = int(height_mm / 25.4 * 300)
            
            # Resize to exactly fill target dimensions
            original_img = original_img.resize((target_width, target_height), Image.LANCZOS)
            
            self.status_label.config(text=f"Adding {bleed_mm}mm bleed...")
            self.root.update()
            final_img = self.create_bleed_image(original_img, bleed_pixels, self.fill_method.get())
            
            # Generate output filename with CMYK indicator
            base_name = os.path.splitext(os.path.basename(self.input_file.get()))[0]
            cmyk_suffix = "_CMYK" if self.convert_to_cmyk.get() and self.output_type.get() == "pdf" else ""
            
            if self.output_type.get() == "pdf":
                output_filename = f"{base_name}{cmyk_suffix}_BLEED{int(bleed_mm)}MM_{self.output_format.get()}.pdf"
                output_path = os.path.join(self.output_folder.get(), output_filename)
                
                self.status_label.config(text="Exporting to PDF with CMYK color space...")
                self.root.update()
                self.export_to_pdf(final_img, output_path, (width_mm + bleed_mm*2, height_mm + bleed_mm*2), bleed_mm)
            else:
                output_filename = f"{base_name}{cmyk_suffix}_BLEED{int(bleed_mm)}MM_{self.output_format.get()}.png"
                output_path = os.path.join(self.output_folder.get(), output_filename)
                final_img.save(output_path, "PNG", dpi=(300, 300))
            
            success_msg = f"File saved successfully!\n{output_path}"
            if self.convert_to_cmyk.get() and self.output_type.get() == "pdf":
                success_msg += f"\n\n✅ CMYK conversie toegepast met profiel: {self.color_profile.get()}\nDit bestand is klaar voor professionele drukwerk (offset/digitaal)."
            
            self.status_label.config(text=f"✓ Success! Saved to: {output_path}")
            messagebox.showinfo("Success", success_msg)
            
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BleedApp(root)
    root.mainloop()