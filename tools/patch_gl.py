#!/usr/bin/env python3
"""Make the 3D park renderer upload GL_FLOAT vertices instead of GL_SHORT.

usage: patch_gl.py <apktool output dir>

The client stores mesh positions/texcoords as 16-bit ints (GL_SHORT) and scales
them with the model and texture matrices. Newer GPU drivers (seen on AMD RDNA4 /
Mesa 26) draw nothing for these unnormalised short attributes, so the park world
stays an empty green screen. Same numbers as floats render everywhere.

Patches dk/progressivemedia/a/f/a/h (mesh upload) and .../i (draw).
"""
import os
import sys

TO_FLOATS = """
.method public static tpFloats([S)[F
    .locals 4

    array-length v0, p0

    new-array v1, v0, [F

    const/4 v2, 0x0

    :tp_loop
    if-ge v2, v0, :tp_done

    aget-short v3, p0, v2

    int-to-float v3, v3

    aput v3, v1, v2

    add-int/lit8 v2, v2, 0x1

    goto :tp_loop

    :tp_done
    return-object v1
.end method
"""


def sub(text, old, new, count=1):
    if text.count(old) != count:
        sys.exit("patch_gl: expected %d match(es) for %r, found %d" % (count, old, text.count(old)))
    return text.replace(old, new)


def main():
    base = os.path.join(sys.argv[1], "smali", "dk", "progressivemedia", "a", "f", "a")

    p = os.path.join(base, "h.smali")
    s = open(p).read()
    if "tpFloats" not in s:
        # stride in bytes: 2 per short -> 4 per float
        s = sub(s, """    :cond_b
    mul-int/lit8 v1, v1, 0x2
""", """    :cond_b
    mul-int/lit8 v1, v1, 0x4
""")
        # buffer size = stride * vertex count
        s = sub(s, """    invoke-static {v9}, Ljava/nio/ByteBuffer;->allocateDirect(I)Ljava/nio/ByteBuffer;
""", """    move-object/from16 v0, p0

    iget v9, v0, Ldk/progressivemedia/a/f/a/h;->c:I

    iget v2, v0, Ldk/progressivemedia/a/f/a/h;->b:I

    mul-int/2addr v9, v2

    invoke-static {v9}, Ljava/nio/ByteBuffer;->allocateDirect(I)Ljava/nio/ByteBuffer;
""")
        s = sub(s, """    invoke-virtual {v1}, Ljava/nio/ByteBuffer;->asShortBuffer()Ljava/nio/ShortBuffer;

    move-result-object v1

    invoke-virtual {v1, v12}, Ljava/nio/ShortBuffer;->put([S)Ljava/nio/ShortBuffer;

    const/4 v2, 0x0

    invoke-virtual {v1, v2}, Ljava/nio/ShortBuffer;->position(I)Ljava/nio/Buffer;
""", """    invoke-virtual {v1}, Ljava/nio/ByteBuffer;->asFloatBuffer()Ljava/nio/FloatBuffer;

    move-result-object v1

    invoke-static {v12}, Ldk/progressivemedia/a/f/a/h;->tpFloats([S)[F

    move-result-object v12

    invoke-virtual {v1, v12}, Ljava/nio/FloatBuffer;->put([F)Ljava/nio/FloatBuffer;

    const/4 v2, 0x0

    invoke-virtual {v1, v2}, Ljava/nio/FloatBuffer;->position(I)Ljava/nio/Buffer;
""")
        s += TO_FLOATS
        open(p, "w").write(s)

    p = os.path.join(base, "i.smali")
    s = open(p).read()
    if "const/16 v7, 0x1406" not in s:
        s = sub(s, "    const/16 v7, 0x1402\n", "    const/16 v7, 0x1406\n")  # GL_SHORT -> GL_FLOAT
        s = sub(s, "    mul-int/lit8 v5, v0, 0x2\n", "    mul-int/lit8 v5, v0, 0x4\n")  # normal offset
        s = sub(s, "    mul-int/lit8 v0, v0, 0x2\n\n    invoke-static {v4, v7, v5, v0}",
                "    mul-int/lit8 v0, v0, 0x4\n\n    invoke-static {v4, v7, v5, v0}")  # texcoord offset
        open(p, "w").write(s)
    print("patch_gl: applied")


if __name__ == "__main__":
    main()
