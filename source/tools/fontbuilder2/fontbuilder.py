import cairo
import codecs
import math

import FontLoader
import Packer

# Representation of a rendered glyph
class Glyph(object):
    def __init__(self, ctx, renderstyle, char, idx, face, size):
        self.renderstyle = renderstyle
        self.char = char
        self.idx = idx
        self.face = face
        self.size = size
        self.glyph = (idx, 0, 0)

        if not ctx.get_font_face() == self.face:
            ctx.set_font_face(self.face)
            ctx.set_font_size(self.size)
        extents = ctx.glyph_extents([self.glyph])

        self.xadvance = round(extents[4])

        # Find the bounding box of strokes and/or fills:

        inf = 1e300 * 1e300
        bb = [inf, inf, -inf, -inf]

        if "stroke" in self.renderstyle:
            for (c, w) in self.renderstyle["stroke"]:
                ctx.set_line_width(w)
                ctx.glyph_path([self.glyph])
                e = ctx.stroke_extents()
                bb = (min(bb[0], e[0]), min(bb[1], e[1]), max(bb[2], e[2]), max(bb[3], e[3]))
                ctx.new_path()

        if "fill" in self.renderstyle:
            ctx.glyph_path([self.glyph])
            e = ctx.fill_extents()
            bb = (min(bb[0], e[0]), min(bb[1], e[1]), max(bb[2], e[2]), max(bb[3], e[3]))
            ctx.new_path()

        bb = (math.floor(bb[0]), math.floor(bb[1]), math.ceil(bb[2]), math.ceil(bb[3]))

        self.x0 = -bb[0]
        self.y0 = -bb[1]
        self.w = bb[2] - bb[0]
        self.h = bb[3] - bb[1]

        # Force multiple of 4, to avoid leakage across S3TC blocks
        # (TODO: is this useful?)
        #self.w += (4 - (self.w % 4)) % 4
        #self.h += (4 - (self.h % 4)) % 4

    def pack(self, packer):
        self.pos = packer.Pack(self.w, self.h)

    def render(self, ctx):
        if not ctx.get_font_face() == self.face:
            ctx.set_font_face(self.face)
            ctx.set_font_size(self.size)
        ctx.save()
        ctx.translate(self.x0, self.y0)
        ctx.translate(self.pos.x, self.pos.y)

        # Render each stroke, and then each fill on top of it

        if "stroke" in self.renderstyle:
            for ((r, g, b, a), w) in self.renderstyle["stroke"]:
                ctx.set_line_width(w)
                ctx.set_source_rgba(r, g, b, a)
                ctx.glyph_path([self.glyph])
                ctx.stroke()

        if "fill" in self.renderstyle:
            for (r, g, b, a) in self.renderstyle["fill"]:
                ctx.set_source_rgba(r, g, b, a)
                ctx.glyph_path([self.glyph])
                ctx.fill()

        ctx.restore()

# Load the set of characters contained in the given text file
def load_char_list(filename):
    f = codecs.open(filename, "r", "utf-8")
    chars = f.read()
    f.close()
    return set(chars)

# Construct a Cairo context and surface for rendering text with the given parameters
def setup_context(width, height, renderstyle):
    format = (cairo.FORMAT_ARGB32 if "colour" in renderstyle else cairo.FORMAT_A8)
    surface = cairo.ImageSurface(format, width, height)
    ctx = cairo.Context(surface)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    return ctx, surface

def generate_font(outname, ttfNames, loadopts, size, renderstyle, dsizes):

    faceList = []
    indexList = []
    for i in range(len(ttfNames)):
        (face, indices) = FontLoader.create_cairo_font_face_for_file("../../../binaries/data/tools/fontbuilder/fonts/%s" % ttfNames[i], 0, loadopts)
        faceList.append(face)
        if not ttfNames[i] in dsizes:
            dsizes[ttfNames[i]] = 0
        indexList.append(indices)

    (ctx, _) = setup_context(1, 1, renderstyle)

    # TODO this gets the line height from the default font
    # while entire texts can be in the fallback font
    ctx.set_font_face(faceList[0]);
    ctx.set_font_size(size + dsizes[ttfNames[0]])
    (_, _, linespacing, _, _) = ctx.font_extents()

    # Estimate the 'average' height of text, for vertical center alignment
    charheight = round(ctx.glyph_extents([(indexList[0]("I"), 0.0, 0.0)])[3])

    # Translate all the characters into glyphs
    # (This is inefficient if multiple characters have the same glyph)
    glyphs = []
    #for c in chars:
    for c in range(0x20, 0xFFFE):
        for i in range(len(indexList)):
            idx = indexList[i](unichr(c))
            if c == 0xFFFD and idx == 0: # use "?" if the missing-glyph glyph is missing
                idx = indexList[i]("?")
            if idx:
                glyphs.append(Glyph(ctx, renderstyle, unichr(c), idx, faceList[i], size + dsizes[ttfNames[i]]))
                break

    # Sort by decreasing height (tie-break on decreasing width)
    glyphs.sort(key = lambda g: (-g.h, -g.w))

    # Try various sizes to pack the glyphs into
    sizes = []
    for h in [32, 64, 128, 256, 512, 1024, 2048, 4096]:
        sizes.append((h, h))
        sizes.append((h*2, h))
    sizes.sort(key = lambda (w, h): (w*h, max(w, h))) # prefer smaller and squarer

    for w, h in sizes:
        try:
            # Using the dump pacher usually creates bigger textures, but runs faster
            # In practice the size difference is so small it always ends up in the same size
            packer = Packer.DumbRectanglePacker(w, h)
            #packer = Packer.CygonRectanglePacker(w, h)
            for g in glyphs:
                g.pack(packer)
        except Packer.OutOfSpaceError:
            continue

        ctx, surface = setup_context(w, h, renderstyle)
        for g in glyphs:
			 g.render(ctx)
        surface.write_to_png("%s.png" % outname)

        # Output the .fnt file with all the glyph positions etc
        fnt = open("%s.fnt" % outname, "w")
        fnt.write("101\n")
        fnt.write("%d %d\n" % (w, h))
        fnt.write("%s\n" % ("rgba" if "colour" in renderstyle else "a"))
        fnt.write("%d\n" % len(glyphs))
        fnt.write("%d\n" % linespacing)
        fnt.write("%d\n" % charheight)
        # sorting unneeded, as glyphs are added in increasing order
        #glyphs.sort(key = lambda g: ord(g.char))
        for g in glyphs:
            x0 = g.x0
            y0 = g.y0
            # UGLY HACK: see http://trac.wildfiregames.com/ticket/1039 ;
            # to handle a-macron-acute characters without the hassle of
            # doing proper OpenType GPOS layout (which the  font
            # doesn't support anyway), we'll just shift the combining acute
            # glyph by an arbitrary amount to make it roughly the right
            # place when used after an a-macron glyph.
            if ord(g.char) == 0x0301:
                y0 += charheight/3

            fnt.write("%d %d %d %d %d %d %d %d\n" % (ord(g.char), g.pos.x, h-g.pos.y, g.w, g.h, -x0, y0, g.xadvance))

        fnt.close()

        return
    print "Failed to fit glyphs in texture"

filled = { "fill": [(1, 1, 1, 1)] }
stroked1 = { "colour": True, "stroke": [((0, 0, 0, 1), 2.0), ((0, 0, 0, 1), 2.0)], "fill": [(1, 1, 1, 1)] }
stroked2 = { "colour": True, "stroke": [((0, 0, 0, 1), 2.0)], "fill": [(1, 1, 1, 1), (1, 1, 1, 1)] }
stroked3 = { "colour": True, "stroke": [((0, 0, 0, 1), 2.5)], "fill": [(1, 1, 1, 1), (1, 1, 1, 1)] }

# For extra glyph support, add your preferred font to the font array
Orkney = (["Orkney Regular.ttf","FreeMono.ttf"], FontLoader.FT_LOAD_DEFAULT)
SourceCodePro = (["SourceCodePro-Regular.ttf","FreeMono.ttf"], FontLoader.FT_LOAD_DEFAULT)
CodeNewRoman = (["cnr.otf","FreeMono.ttf"], FontLoader.FT_LOAD_DEFAULT)

OrbitronBlack = (["orbitron-black.otf","FreeMono.ttf"], FontLoader.FT_LOAD_DEFAULT)
OrbitronBold = (["orbitron-bold.otf","FreeMono.ttf"], FontLoader.FT_LOAD_DEFAULT)
OrbitronLight = (["orbitron-light.otf","FreeMono.ttf"], FontLoader.FT_LOAD_DEFAULT)
OrbitronMedium = (["orbitron-medium.otf","FreeMono.ttf"], FontLoader.FT_LOAD_DEFAULT)


# Define the size differences used to render different fallback fonts
# I.e. when adding a fallback font has smaller glyphs than the original, you can bump it
dsizes = {'HanaMinA.ttf': 2} # make the glyphs for the (chinese font 2 pts bigger)

fonts = (
    ("orkney-12", Orkney, 12, filled),
    ("orkney-14", Orkney, 14, filled),
    ("orkney-16", Orkney, 16, filled),
    ("orkney-18", Orkney, 18, filled),
    ("orkney-20", Orkney, 20, filled),
    ("orkney-22", Orkney, 22, filled),
    ("sourcecodepro-12", SourceCodePro, 12, filled),
    ("sourcecodepro-14", SourceCodePro, 14, filled),
    ("sourcecodepro-16", SourceCodePro, 16, filled),
    ("sourcecodepro-18", SourceCodePro, 18, filled),
    ("sourcecodepro-20", SourceCodePro, 20, filled),
    ("sourcecodepro-22", SourceCodePro, 22, filled),
    ("codenewroman-12", CodeNewRoman, 12, filled),
    ("codenewroman-14", CodeNewRoman, 14, filled),
    ("codenewroman-16", CodeNewRoman, 16, filled),
    ("codenewroman-18", CodeNewRoman, 18, filled),
    ("codenewroman-20", CodeNewRoman, 20, filled),
    ("codenewroman-22", CodeNewRoman, 22, filled),

    ("orbitron-black-12", OrbitronBlack, 12, filled),
    ("orbitron-black-14", OrbitronBlack, 14, filled),
    ("orbitron-black-16", OrbitronBlack, 16, filled),
    ("orbitron-black-18", OrbitronBlack, 18, filled),
    ("orbitron-black-20", OrbitronBlack, 20, filled),
    ("orbitron-black-22", OrbitronBlack, 22, filled),

    ("orbitron-bold-12", OrbitronBold, 12, filled),
    ("orbitron-bold-14", OrbitronBold, 14, filled),
    ("orbitron-bold-16", OrbitronBold, 16, filled),
    ("orbitron-bold-18", OrbitronBold, 18, filled),
    ("orbitron-bold-20", OrbitronBold, 20, filled),
    ("orbitron-bold-22", OrbitronBold, 22, filled),

    ("orbitron-light-12", OrbitronLight, 12, filled),
    ("orbitron-light-14", OrbitronLight, 14, filled),
    ("orbitron-light-16", OrbitronLight, 16, filled),
    ("orbitron-light-18", OrbitronLight, 18, filled),
    ("orbitron-light-20", OrbitronLight, 20, filled),
    ("orbitron-light-22", OrbitronLight, 22, filled),

    ("orbitron-medium-12", OrbitronMedium, 12, filled),
    ("orbitron-medium-14", OrbitronMedium, 14, filled),
    ("orbitron-medium-16", OrbitronMedium, 16, filled),
    ("orbitron-medium-18", OrbitronMedium, 18, filled),
    ("orbitron-medium-20", OrbitronMedium, 20, filled),
    ("orbitron-medium-22", OrbitronMedium, 22, filled),
)

for (name, (fontnames, loadopts), size, style) in fonts:
    print "%s..." % name
    generate_font("../../../binaries/data/mods/mod/fonts/%s" % name, fontnames, loadopts, size, style, dsizes)
