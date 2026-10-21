"""One-page RGB PDF: write image streams immediately, with bounded image memory.

Cross-reference streams use 64-bit offsets, including for PDFs larger than 10 GB.
Only object offsets, image references and drawing commands remain in memory.
"""
import zlib

def text(value):
    return b'<' + (b'\xfe\xff'+value.encode('utf-16-be')).hex().encode() + b'>'

class RasterPDF:
    def __init__(self,stream,width,height,title,subject):
        self.f=stream; self.offsets={}; self.next=6; self.images=[]; self.commands=[]
        self.width=width; self.height=height
        self.f.write(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')
        self.obj(1,b'<< /Type /Catalog /Pages 2 0 R >>')
        self.obj(2,b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
        self.obj(4,b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
        self.obj(5,b'<< /Title '+text(title)+b' /Author '+text('Aarhus Plotter')+b' /Subject '+text(subject)+b' >>')

    def obj(self,id,body):
        self.offsets[id]=self.f.tell()
        self.f.write(f'{id} 0 obj\n'.encode());self.f.write(body);self.f.write(b'\nendobj\n')

    def stream(self,id,attrs,data):
        self.offsets[id]=self.f.tell()
        self.f.write(f'{id} 0 obj\n<< '.encode()+attrs+f' /Length {len(data)} >>\nstream\n'.encode())
        self.f.write(data);self.f.write(b'\nendstream\nendobj\n')

    def image(self,rgb,width,height,x,y,draw_width,draw_height):
        id=self.next;self.next+=1;name=f'Im{id}'
        assert len(rgb)==width*height*3
        attrs=f'/Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Interpolate false /Filter /FlateDecode'.encode()
        self.stream(id,attrs,zlib.compress(rgb,6))
        self.images.append(f'/{name} {id} 0 R')
        self.commands.append(f'q {draw_width:.8f} 0 0 {draw_height:.8f} {x:.8f} {y:.8f} cm /{name} Do Q\n')

    def finish(self,footer):
        footer_hex=footer.encode('cp1252',errors='replace').hex()
        self.commands.append(f'BT /F1 7 Tf 0.3 g 22.67716535 8.50393701 Td <{footer_hex}> Tj ET\n')
        content=self.next;self.next+=1
        self.stream(content,b'/Filter /FlateDecode',zlib.compress(''.join(self.commands).encode('ascii')))
        self.obj(3,f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width:.8f} {self.height:.8f}] /Resources << /Font << /F1 4 0 R >> /XObject << {" ".join(self.images)} >> >> /Contents {content} 0 R >>'.encode())
        xref=self.next;start=self.f.tell();self.offsets[xref]=start
        size=xref+1
        rows=bytearray(b'\x00'+bytes(8)+b'\xff\xff')
        for id in range(1,size):rows.extend(b'\x01'+self.offsets[id].to_bytes(8,'big')+b'\x00\x00')
        self.stream(xref,f'/Type /XRef /Size {size} /W [1 8 2] /Root 1 0 R /Info 5 0 R /Filter /FlateDecode'.encode(),zlib.compress(rows))
        self.f.write(f'startxref\n{start}\n%%EOF\n'.encode())
