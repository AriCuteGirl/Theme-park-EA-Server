package dk.progressivemedia.android;

import android.opengl.GLES11;
import android.opengl.GLES11Ext;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.nio.ShortBuffer;

/**
 * Pure-Java replacement for librflib.so (32-bit ARM only), so the game runs on
 * 64-bit-only phones. Mirrors the native PMGraphics/PMOpenGL batching:
 * sprites are quads in target-pixel space, colours are tint/colour premultiplied
 * by alpha, and a batch is flushed whenever its kind or texture changes, so draw
 * order is preserved. Vertices are floats instead of 16.16 fixed point.
 */
public class PMGraphics {
    // Batch kinds (match the native flush functions).
    private static final int NONE = 0, TEXTURED = 1, TEXTURED_ALPHA = 2, COLORED = 3, COLORED_ALPHA = 4, LINES = 5;

    private static final int MAX_QUADS = 2048;
    // x, y, z, u, v + packed RGBA colour in a separate buffer
    private static final FloatBuffer pos = alloc(MAX_QUADS * 4 * 3 * 4).asFloatBuffer();
    private static final FloatBuffer tex = alloc(MAX_QUADS * 4 * 2 * 4).asFloatBuffer();
    private static final ByteBuffer col = alloc(MAX_QUADS * 4 * 4);
    private static final ShortBuffer idx = alloc(MAX_QUADS * 6 * 2).asShortBuffer();
    private static int verts = 0;
    private static int indices = 0;
    private static int batch = NONE;
    private static int batchTex = 0;
    private static int batchMode = 0;
    private static int batchPrim = GLES11.GL_TRIANGLES;

    // Colour state: colour (primitives), tint (images), alpha.
    private static int colR = 255, colG = 255, colB = 255;
    private static int tintR = 255, tintG = 255, tintB = 255;
    private static int alpha = 255;
    private static int targetW = 480, targetH = 320;

    // GL state caches (the Java renderer relies on these, like the native ones).
    private static boolean vertexArray, texCoordArray, normalArray, colorArray, texture2D, blend, alphaTest;
    private static int boundTexture = 0;

    private static ByteBuffer alloc(int n) {
        return ByteBuffer.allocateDirect(n).order(ByteOrder.nativeOrder());
    }

    public static void init() {
        verts = indices = 0;
        batch = NONE;
        boundTexture = 0;
    }

    public static void setTargetSize(int w, int h) {
        targetW = w;
        targetH = h;
    }

    public static void setColor(int rgb) {
        setColor((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255);
    }

    public static void setColor(int r, int g, int b) {
        colR = r & 255;
        colG = g & 255;
        colB = b & 255;
    }

    public static int getColor() {
        return (colR << 16) | (colG << 8) | colB;
    }

    public static void setTint(int r, int g, int b) {
        tintR = r & 255;
        tintG = g & 255;
        tintB = b & 255;
    }

    public static void setAlpha(int a) {
        alpha = a & 255;
    }

    // ---- GL state helpers -------------------------------------------------

    private static void clientState(int cap, boolean on) {
        if (on) {
            GLES11.glEnableClientState(cap);
        } else {
            GLES11.glDisableClientState(cap);
        }
    }

    private static void capability(int cap, boolean on) {
        if (on) {
            GLES11.glEnable(cap);
        } else {
            GLES11.glDisable(cap);
        }
    }

    public static void setVertexArrayEnabled(boolean z) {
        if (vertexArray != z) {
            vertexArray = z;
            clientState(GLES11.GL_VERTEX_ARRAY, z);
        }
    }

    public static void setTexCoordArrayEnabled(boolean z) {
        if (texCoordArray != z) {
            texCoordArray = z;
            clientState(GLES11.GL_TEXTURE_COORD_ARRAY, z);
        }
    }

    public static void setNormalArrayEnabled(boolean z) {
        if (normalArray != z) {
            normalArray = z;
            clientState(GLES11.GL_NORMAL_ARRAY, z);
        }
    }

    public static void setColorArrayEnabled(boolean z) {
        if (colorArray != z) {
            colorArray = z;
            clientState(GLES11.GL_COLOR_ARRAY, z);
        }
    }

    public static void setTexture2DEnabled(boolean z) {
        if (texture2D != z) {
            texture2D = z;
            capability(GLES11.GL_TEXTURE_2D, z);
        }
    }

    public static void setAlphaBlendEnabled(boolean z) {
        if (blend != z) {
            blend = z;
            capability(GLES11.GL_BLEND, z);
        }
    }

    public static void setAlphaTestEnabled(boolean z) {
        if (alphaTest != z) {
            alphaTest = z;
            capability(GLES11.GL_ALPHA_TEST, z);
        }
    }

    public static int getTexture() {
        return boundTexture;
    }

    public static void setTexture(int t) {
        if (t != boundTexture) {
            boundTexture = t;
            GLES11.glBindTexture(GLES11.GL_TEXTURE_2D, t);
        }
    }

    public static void glGenerateMipmapOES() {
        GLES11Ext.glGenerateMipmapOES(GLES11.GL_TEXTURE_2D);
    }

    public static void resetStates() {
        alpha = 255;
        blend = alphaTest = texture2D = true;
        setAlphaBlendEnabled(false);
        setAlphaTestEnabled(false);
        setTexture2DEnabled(false);
        colorArray = texCoordArray = normalArray = true;
        vertexArray = false;
        setColorArrayEnabled(false);
        setTexCoordArrayEnabled(false);
        setVertexArrayEnabled(true);
        setNormalArrayEnabled(false);
        if (boundTexture != 0) {
            boundTexture = 0;
            GLES11.glBindTexture(GLES11.GL_TEXTURE_2D, 0);
        }
    }

    public static void reset2DBuffers() {
        flushBuffer();
    }

    // ---- batching -----------------------------------------------------------

    private static void begin(int kind, int texture, int mode, int prim, int nverts, int nidx) {
        if (batch != kind || (texture != batchTex && (kind == TEXTURED || kind == TEXTURED_ALPHA))
                || (kind == TEXTURED && mode != batchMode) || prim != batchPrim
                || verts + nverts > MAX_QUADS * 4 || indices + nidx > MAX_QUADS * 6) {
            flushBuffer();
        }
        batch = kind;
        batchTex = texture;
        batchMode = mode;
        batchPrim = prim;
    }

    private static void vertex(float x, float y, float u, float v, int rgba) {
        int i = verts;
        pos.put(i * 3, x);
        pos.put(i * 3 + 1, y);
        pos.put(i * 3 + 2, 0.5f);
        tex.put(i * 2, u);
        tex.put(i * 2 + 1, v);
        col.put(i * 4, (byte) (rgba & 255));
        col.put(i * 4 + 1, (byte) ((rgba >> 8) & 255));
        col.put(i * 4 + 2, (byte) ((rgba >> 16) & 255));
        col.put(i * 4 + 3, (byte) ((rgba >>> 24) & 255));
        verts++;
    }

    private static void quadIndices(int base) {
        idx.put(indices++, (short) base);
        idx.put(indices++, (short) (base + 1));
        idx.put(indices++, (short) (base + 2));
        idx.put(indices++, (short) (base + 1));
        idx.put(indices++, (short) (base + 3));
        idx.put(indices++, (short) (base + 2));
    }

    public static void flushBuffer() {
        if (batch == NONE || indices == 0) {
            verts = indices = 0;
            batch = NONE;
            return;
        }
        boolean textured = batch == TEXTURED || batch == TEXTURED_ALPHA;
        setVertexArrayEnabled(true);
        setColorArrayEnabled(true);
        setNormalArrayEnabled(false);
        setTexCoordArrayEnabled(textured);
        setTexture2DEnabled(textured);
        switch (batch) {
            case TEXTURED:
                setAlphaBlendEnabled(false);
                setAlphaTestEnabled(batchMode != 0);
                break;
            case TEXTURED_ALPHA:
            case COLORED_ALPHA:
                setAlphaBlendEnabled(true);
                setAlphaTestEnabled(false);
                break;
            default:
                setAlphaBlendEnabled(false);
                setAlphaTestEnabled(false);
                break;
        }
        GLES11.glBindBuffer(GLES11.GL_ARRAY_BUFFER, 0);
        pos.position(0);
        col.position(0);
        tex.position(0);
        idx.position(0);
        GLES11.glVertexPointer(3, GLES11.GL_FLOAT, 0, pos);
        GLES11.glColorPointer(4, GLES11.GL_UNSIGNED_BYTE, 0, col);
        if (textured) {
            GLES11.glTexCoordPointer(2, GLES11.GL_FLOAT, 0, tex);
            setTexture(batchTex);
        }
        GLES11.glDrawElements(batchPrim, indices, GLES11.GL_UNSIGNED_SHORT, idx);
        verts = indices = 0;
        batch = NONE;
    }

    private static int premultiply(int r, int g, int b, int a) {
        if (a == 255) {
            return 0xFF000000 | (b << 16) | (g << 8) | r;
        }
        return (a << 24) | ((b * a / 255) << 16) | ((g * a / 255) << 8) | (r * a / 255);
    }

    private static final float FX = 1f / 65536f;

    /** Shared by drawImage/drawImagef once everything is in pixels/radians. */
    private static void sprite(int texture, int mode, float w, float h, float ax, float ay,
                               float u0, float v0, float u1, float v1, float x, float y,
                               boolean flip, float angle, int a, float sx, float sy) {
        if (flip) {
            ax = w - ax;
            float t = u0;
            u0 = u1;
            u1 = t;
        }
        float[] px = {-ax, w - ax, -ax, w - ax};
        float[] py = {-ay, -ay, h - ay, h - ay};
        float c = 1f, s = 0f;
        boolean rot = angle != 0f;
        if (rot) {
            c = (float) Math.cos(angle);
            s = (float) Math.sin(angle);
        }
        boolean anyInX = false, anyInY = false;
        for (int i = 0; i < 4; i++) {
            float vx = px[i] * sx, vy = py[i] * sy;
            if (rot) {
                float rx = vx * c - vy * s;
                vy = vx * s + vy * c;
                vx = rx;
            }
            px[i] = vx + x;
            py[i] = vy + y;
            if (px[i] >= 0 && px[i] < targetW) anyInX = true;
            if (py[i] >= 0 && py[i] < targetH) anyInY = true;
        }
        // Native code skipped quads entirely off one side of the target.
        if (allBelow(px, 0) || allAbove(px, targetW) || allBelow(py, 0) || allAbove(py, targetH)) {
            return;
        }
        boolean opaque = mode != 2 && a == 255;
        int rgba = premultiply(tintR, tintG, tintB, a);
        begin(opaque ? TEXTURED : TEXTURED_ALPHA, texture, mode, GLES11.GL_TRIANGLES, 4, 6);
        int base = verts;
        vertex(px[0], py[0], u0, v0, rgba);
        vertex(px[1], py[1], u1, v0, rgba);
        vertex(px[2], py[2], u0, v1, rgba);
        vertex(px[3], py[3], u1, v1, rgba);
        quadIndices(base);
    }

    private static boolean allBelow(float[] v, float lim) {
        for (float f : v) if (f >= lim) return false;
        return true;
    }

    private static boolean allAbove(float[] v, float lim) {
        for (float f : v) if (f < lim) return false;
        return true;
    }

    /**
     * texture, alphaMode (0 opaque, 2 alpha), width, height, anchorX, anchorY,
     * u0, v0, u1, v1 (16.16), x, y, flip, rotation (degrees), alpha (0-255),
     * scaleX, scaleY (16.16).
     */
    public static void drawImage(int texture, int mode, short w, short h, short ax, short ay,
                                 int u0, int v0, int u1, int v1, int x, int y, boolean flip,
                                 int rotDeg, int a, int sx, int sy) {
        int tintA = Math.max(0, Math.min(255, a));
        sprite(texture, mode, w, h, ax, ay, u0 * FX, v0 * FX, u1 * FX, v1 * FX, x, y, flip,
                rotDeg == 0 ? 0f : (float) Math.toRadians(rotDeg), tintA, sx * FX, sy * FX);
    }

    /** Same as drawImage with float position, rotation as a fraction of a turn, alpha 0-1. */
    public static void drawImagef(int texture, int mode, short w, short h, short ax, short ay,
                                  int u0, int v0, int u1, int v1, float x, float y, boolean flip,
                                  float rot, float a, float sx, float sy) {
        int ia = a >= 0.999f ? 255 : Math.max(0, (int) (a * 255f));
        float angle = (rot > 0.001f || rot < -0.001f) ? rot * 6.2831855f : 0f;
        sprite(texture, mode, w, h, ax, ay, u0 * FX, v0 * FX, u1 * FX, v1 * FX, x, y, flip,
                angle, ia, sx, sy);
    }

    // ---- primitives -----------------------------------------------------------

    private static int primColor() {
        return premultiply(colR, colG, colB, alpha);
    }

    public static void fillRect(int x, int y, int w, int h) {
        if (w <= 0 || h <= 0 || x > targetW || y > targetH) {
            return;
        }
        int rgba = primColor();
        begin(alpha == 255 ? COLORED : COLORED_ALPHA, 0, 0, GLES11.GL_TRIANGLES, 4, 6);
        int base = verts;
        vertex(x, y, 0, 0, rgba);
        vertex(x + w, y, 0, 0, rgba);
        vertex(x, y + h, 0, 0, rgba);
        vertex(x + w, y + h, 0, 0, rgba);
        quadIndices(base);
    }

    public static void fillTriangle(int x1, int y1, int x2, int y2, int x3, int y3) {
        int rgba = primColor();
        begin(alpha == 255 ? COLORED : COLORED_ALPHA, 0, 0, GLES11.GL_TRIANGLES, 3, 3);
        int base = verts;
        vertex(x1, y1, 0, 0, rgba);
        vertex(x2, y2, 0, 0, rgba);
        vertex(x3, y3, 0, 0, rgba);
        idx.put(indices++, (short) base);
        idx.put(indices++, (short) (base + 1));
        idx.put(indices++, (short) (base + 2));
    }

    public static void drawLine(int x1, int y1, int x2, int y2) {
        int rgba = primColor();
        begin(LINES, 0, 0, GLES11.GL_LINES, 2, 2);
        int base = verts;
        vertex(x1 + 0.5f, y1 + 0.5f, 0, 0, rgba);
        vertex(x2 + 0.5f, y2 + 0.5f, 0, 0, rgba);
        idx.put(indices++, (short) base);
        idx.put(indices++, (short) (base + 1));
    }

    public static void drawRect(int x, int y, int w, int h) {
        drawLine(x, y, x + w, y);
        drawLine(x + w, y, x + w, y + h);
        drawLine(x + w, y + h, x, y + h);
        drawLine(x, y + h, x, y);
    }

    private static final int SEGMENTS = 32;

    public static void fillArc(int x, int y, int w, int h, int start, int arc) {
        float cx = x + w / 2f, cy = y + h / 2f, rx = w / 2f, ry = h / 2f;
        int segs = Math.max(4, SEGMENTS * Math.abs(arc) / 360);
        double a0 = Math.toRadians(-start), step = Math.toRadians(-arc) / segs;
        float px = cx + (float) Math.cos(a0) * rx, py = cy + (float) Math.sin(a0) * ry;
        for (int i = 1; i <= segs; i++) {
            double t = a0 + step * i;
            float nx = cx + (float) Math.cos(t) * rx, ny = cy + (float) Math.sin(t) * ry;
            fillTriangle(Math.round(cx), Math.round(cy), Math.round(px), Math.round(py),
                    Math.round(nx), Math.round(ny));
            px = nx;
            py = ny;
        }
    }

    public static void drawArc(int x, int y, int w, int h, int start, int arc) {
        float cx = x + w / 2f, cy = y + h / 2f, rx = w / 2f, ry = h / 2f;
        int segs = Math.max(4, SEGMENTS * Math.abs(arc) / 360);
        double a0 = Math.toRadians(-start), step = Math.toRadians(-arc) / segs;
        int px = Math.round(cx + (float) Math.cos(a0) * rx), py = Math.round(cy + (float) Math.sin(a0) * ry);
        for (int i = 1; i <= segs; i++) {
            double t = a0 + step * i;
            int nx = Math.round(cx + (float) Math.cos(t) * rx), ny = Math.round(cy + (float) Math.sin(t) * ry);
            drawLine(px, py, nx, ny);
            px = nx;
            py = ny;
        }
    }

    public static void fillCircle(int x, int y, int r) {
        fillArc(x - r, y - r, r * 2, r * 2, 0, 360);
    }

    public static void drawCircle(int x, int y, int r) {
        drawArc(x - r, y - r, r * 2, r * 2, 0, 360);
    }
}
