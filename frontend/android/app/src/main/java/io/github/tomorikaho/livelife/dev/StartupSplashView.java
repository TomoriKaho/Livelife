package io.github.tomorikaho.livelife.dev;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.LinearInterpolator;
import android.view.animation.PathInterpolator;
import android.webkit.WebView;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.getcapacitor.BridgeActivity;

/** Native startup splash matching the browser splash in frontend/index.html. */
public class StartupSplashView extends FrameLayout {
    private static final int YELLOW = 0xFFFDE554;
    private static final int INK = 0xFF20304B;
    private static final int BUTTON = 0xFF398DEF;
    private static final int PAPER = 0xFFF8F4EA;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final StartupLogoView logo;
    private final View loading;
    private final TextView[] dots = new TextView[3];
    private final View error;
    private final boolean motionAllowed;
    private ValueAnimator floatAnimator;
    private ValueAnimator strokeAnimator;
    private ValueAnimator dotAnimator;
    private boolean dismissed;

    public StartupSplashView(Context context) {
        super(context);
        motionAllowed = motionAllowed(context);
        setBackgroundColor(YELLOW);
        setClickable(true);
        setContentDescription("Livelife 加载中");

        LinearLayout column = new LinearLayout(context);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setGravity(Gravity.CENTER_HORIZONTAL);
        column.setTranslationY(-dp(10));

        logo = new StartupLogoView(context);
        int size = Math.min(Math.round(getResources().getDisplayMetrics().widthPixels * 0.46f), dp(210));
        column.addView(logo, new LinearLayout.LayoutParams(size, size));

        loading = loadingRow(context);
        LinearLayout.LayoutParams loadingParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        );
        loadingParams.topMargin = -dp(2);
        column.addView(loading, loadingParams);

        error = errorBlock(context);
        column.addView(error, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        addView(column, new LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
            Gravity.CENTER
        ));
        startMotion();
        handler.postDelayed(() -> loading.setVisibility(VISIBLE), 1000);
        handler.postDelayed(this::showError, 15000);
    }

    public void showError() {
        if (dismissed || error.getVisibility() == VISIBLE) return;
        handler.removeCallbacksAndMessages(null);
        pauseMotion();
        loading.setVisibility(GONE);
        error.setVisibility(VISIBLE);
        setContentDescription("启动时间较长，请重试。");
    }

    public void dismiss() {
        if (dismissed) return;
        dismissed = true;
        handler.removeCallbacksAndMessages(null);
        stopMotion();
        if (!motionAllowed) {
            removeSelf();
            return;
        }
        animate().alpha(0f).setDuration(180).setListener(new AnimatorListenerAdapter() {
            @Override
            public void onAnimationEnd(Animator animation) {
                removeSelf();
            }
        }).start();
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        if (w <= 0) return;
        int size = Math.min(Math.round(w * 0.46f), dp(210));
        ViewGroup.LayoutParams params = logo.getLayoutParams();
        if (params.width == size) return;
        params.width = size;
        params.height = size;
        logo.setLayoutParams(params);
    }

    @Override
    protected void onDetachedFromWindow() {
        handler.removeCallbacksAndMessages(null);
        stopMotion();
        super.onDetachedFromWindow();
    }

    private View loadingRow(Context context) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_HORIZONTAL);
        row.setBaselineAligned(true);
        row.setVisibility(INVISIBLE);
        TextView label = label(context, "加载中", 23);
        label.setLetterSpacing(0.05f);
        row.addView(label);
        for (int i = 0; i < dots.length; i++) {
            dots[i] = label(context, ".", 23);
            dots[i].setAlpha(motionAllowed ? 0f : 1f);
            row.addView(dots[i]);
        }
        return row;
    }

    private View errorBlock(Context context) {
        LinearLayout block = new LinearLayout(context);
        block.setOrientation(LinearLayout.VERTICAL);
        block.setGravity(Gravity.CENTER_HORIZONTAL);
        block.setVisibility(GONE);
        TextView message = label(context, "启动时间较长，请重试。", 14);
        LinearLayout.LayoutParams messageParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        );
        messageParams.topMargin = dp(18);
        messageParams.bottomMargin = dp(10);
        block.addView(message, messageParams);

        TextView retry = label(context, "重新加载", 14);
        retry.setTextColor(Color.WHITE);
        retry.setGravity(Gravity.CENTER);
        retry.setMinHeight(dp(44));
        retry.setMinimumHeight(dp(44));
        retry.setPadding(dp(18), dp(7), dp(18), dp(7));
        retry.setClickable(true);
        retry.setFocusable(true);
        GradientDrawable background = new GradientDrawable();
        background.setColor(BUTTON);
        background.setCornerRadius(dp(10));
        background.setStroke(Math.max(1, dp(1)), INK);
        retry.setBackground(background);
        retry.setOnClickListener(v -> reload());
        block.addView(retry, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ));
        return block;
    }

    private TextView label(Context context, String text, float sizeSp) {
        TextView view = new TextView(context);
        view.setText(text);
        view.setTextColor(INK);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp);
        view.setIncludeFontPadding(false);
        return view;
    }

    private void reload() {
        if (!(getContext() instanceof BridgeActivity)) return;
        BridgeActivity activity = (BridgeActivity) getContext();
        if (activity.getBridge() == null || activity.getBridge().getWebView() == null) return;
        WebView webView = activity.getBridge().getWebView();
        webView.setBackgroundColor(YELLOW);
        webView.reload();
        error.setVisibility(GONE);
        loading.setVisibility(INVISIBLE);
        for (TextView dot : dots) dot.setAlpha(motionAllowed ? 0f : 1f);
        logo.setStrokeAlpha(1f);
        setContentDescription("Livelife 加载中");
        startMotion();
        handler.removeCallbacksAndMessages(null);
        handler.postDelayed(() -> loading.setVisibility(VISIBLE), 1000);
        handler.postDelayed(this::showError, 15000);
    }

    private void startMotion() {
        stopMotion();
        if (!motionAllowed) {
            logo.setStrokeAlpha(1f);
            return;
        }
        floatAnimator = ValueAnimator.ofFloat(dp(5), -dp(6));
        floatAnimator.setDuration(1600);
        floatAnimator.setStartDelay(550);
        floatAnimator.setInterpolator(easeInOut());
        floatAnimator.setRepeatMode(ValueAnimator.REVERSE);
        floatAnimator.setRepeatCount(ValueAnimator.INFINITE);
        floatAnimator.addUpdateListener(animation -> logo.setTranslationY((float) animation.getAnimatedValue()));
        floatAnimator.start();

        strokeAnimator = ValueAnimator.ofFloat(1f, 0f);
        strokeAnimator.setDuration(1000);
        strokeAnimator.setStartDelay(550);
        strokeAnimator.setInterpolator(easeInOut());
        strokeAnimator.setRepeatMode(ValueAnimator.REVERSE);
        strokeAnimator.setRepeatCount(ValueAnimator.INFINITE);
        strokeAnimator.addUpdateListener(animation -> logo.setStrokeAlpha((float) animation.getAnimatedValue()));
        strokeAnimator.start();

        dotAnimator = ValueAnimator.ofFloat(0f, 1f);
        dotAnimator.setDuration(1800);
        dotAnimator.setInterpolator(new LinearInterpolator());
        dotAnimator.setRepeatCount(ValueAnimator.INFINITE);
        dotAnimator.addUpdateListener(animation -> {
            float t = (float) animation.getAnimatedValue();
            dots[0].setAlpha(t >= 0.15f && t <= 0.84f ? 1f : 0f);
            dots[1].setAlpha(t >= 0.35f && t <= 0.84f ? 1f : 0f);
            dots[2].setAlpha(t >= 0.55f && t <= 0.84f ? 1f : 0f);
        });
        dotAnimator.start();
    }

    private void pauseMotion() {
        if (floatAnimator != null) floatAnimator.pause();
        if (strokeAnimator != null) strokeAnimator.pause();
        if (dotAnimator != null) dotAnimator.pause();
    }

    private void stopMotion() {
        if (floatAnimator != null) floatAnimator.cancel();
        if (strokeAnimator != null) strokeAnimator.cancel();
        if (dotAnimator != null) dotAnimator.cancel();
        floatAnimator = null;
        strokeAnimator = null;
        dotAnimator = null;
    }

    private void removeSelf() {
        if (getContext() instanceof BridgeActivity) {
            BridgeActivity activity = (BridgeActivity) getContext();
            if (activity.getBridge() != null && activity.getBridge().getWebView() != null) {
                activity.getBridge().getWebView().setBackgroundColor(PAPER);
            }
        }
        ViewGroup parent = (ViewGroup) getParent();
        if (parent != null) parent.removeView(this);
        StartupSplashPlugin.onDismissed(this);
    }

    private int dp(float value) {
        return Math.round(TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP,
            value,
            getResources().getDisplayMetrics()
        ));
    }

    private static PathInterpolator easeInOut() {
        return new PathInterpolator(0.42f, 0f, 0.58f, 1f);
    }

    private static boolean motionAllowed(Context context) {
        float scale = Settings.Global.getFloat(
            context.getContentResolver(),
            Settings.Global.ANIMATOR_DURATION_SCALE,
            1f
        );
        return scale > 0f;
    }
}
