package io.github.tomorikaho.livelife.dev;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffXfermode;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.util.AttributeSet;
import android.view.View;

/**
 * Draws the startup balloon with the same stroke mask as the browser splash.
 * Mask coordinates are the 1254 viewBox in frontend/index.html.
 */
public class StartupLogoView extends View {
    private static final float MASK_SPACE = 1254f;
    private static final String STROKE_PATH =
        "M859 142 874 149 888 169 891 200 884 234 852 298 813 297 795 286 775 258 784 203 813 152 838 141Z "
            + "M1006 248 1022 271 1024 290 1004 328 954 364 908 388 887 388 868 372 852 331 895 277 952 242 981 239Z "
            + "M898 396 918 387 942 388 977 397 1010 414 1031 448 1022 485 1001 501 973 504 907 474 892 461 886 420Z";

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final RectF dest = new RectF();
    private Bitmap base;
    private Bitmap strokes;
    private float strokeAlpha = 1f;

    public StartupLogoView(Context context) {
        this(context, null);
    }

    public StartupLogoView(Context context, AttributeSet attrs) {
        super(context, attrs);
        try {
            prepare();
        } catch (RuntimeException ignored) {
            recycle();
        }
    }

    public void setStrokeAlpha(float alpha) {
        float next = Math.max(0f, Math.min(1f, alpha));
        if (next == strokeAlpha) return;
        strokeAlpha = next;
        invalidate();
    }

    @Override
    protected void onDetachedFromWindow() {
        super.onDetachedFromWindow();
        recycle();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        if (base == null || strokes == null) return;
        dest.set(0, 0, getWidth(), getHeight());
        paint.setAlpha(255);
        canvas.drawBitmap(base, null, dest, paint);
        paint.setAlpha(Math.round(strokeAlpha * 255));
        canvas.drawBitmap(strokes, null, dest, paint);
    }

    private void prepare() {
        Bitmap source = BitmapFactory.decodeResource(getResources(), R.drawable.startup_logo);
        if (source == null) return;
        float scale = source.getWidth() / MASK_SPACE;
        Bitmap mask = maskBitmap(source.getWidth(), source.getHeight(), pathFromSvg(STROKE_PATH, scale));
        base = masked(source, mask, PorterDuff.Mode.DST_OUT);
        strokes = masked(source, mask, PorterDuff.Mode.DST_IN);
        fadeEdges(base);
        fadeEdges(strokes);
        mask.recycle();
    }

    private static Bitmap maskBitmap(int width, int height, Path path) {
        Bitmap mask = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(mask);
        Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
        fill.setStyle(Paint.Style.FILL);
        fill.setColor(Color.BLACK);
        canvas.drawPath(path, fill);
        return mask;
    }

    private static Bitmap masked(Bitmap source, Bitmap mask, PorterDuff.Mode mode) {
        Bitmap result = Bitmap.createBitmap(source.getWidth(), source.getHeight(), Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(result);
        canvas.drawBitmap(source, 0, 0, null);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        paint.setXfermode(new PorterDuffXfermode(mode));
        canvas.drawBitmap(mask, 0, 0, paint);
        return result;
    }

    private static void fadeEdges(Bitmap bitmap) {
        float radius = Math.min(bitmap.getWidth(), bitmap.getHeight()) / 2f;
        RadialGradient gradient = new RadialGradient(
            bitmap.getWidth() / 2f,
            bitmap.getHeight() / 2f,
            radius,
            new int[] { Color.BLACK, Color.BLACK, Color.TRANSPARENT },
            new float[] { 0f, 0.83f, 1f },
            Shader.TileMode.CLAMP
        );
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        paint.setShader(gradient);
        paint.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.DST_IN));
        new Canvas(bitmap).drawRect(0, 0, bitmap.getWidth(), bitmap.getHeight(), paint);
    }

    private static Path pathFromSvg(String data, float scale) {
        Path path = new Path();
        String[] tokens = data.replace("Z", " Z ").replace("M", "M ").trim().split("\\s+");
        int index = 0;
        while (index < tokens.length) {
            String token = tokens[index];
            if (!"M".equals(token)) {
                index++;
                continue;
            }
            index++;
            path.moveTo(Float.parseFloat(tokens[index++]) * scale, Float.parseFloat(tokens[index++]) * scale);
            while (index + 1 < tokens.length && !"Z".equals(tokens[index]) && !"M".equals(tokens[index])) {
                path.lineTo(Float.parseFloat(tokens[index++]) * scale, Float.parseFloat(tokens[index++]) * scale);
            }
            if (index < tokens.length && "Z".equals(tokens[index])) {
                path.close();
                index++;
            }
        }
        return path;
    }

    private void recycle() {
        if (base != null) base.recycle();
        if (strokes != null) strokes.recycle();
        base = null;
        strokes = null;
    }
}
