package ai.smartragents.smartrplay;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.google.android.exoplayer2.ExoPlayer;
import com.google.android.exoplayer2.MediaItem;
import com.google.android.exoplayer2.PlaybackException;
import com.google.android.exoplayer2.Player;
import com.google.android.exoplayer2.source.MediaSource;
import com.google.android.exoplayer2.source.hls.HlsMediaSource;
import com.google.android.exoplayer2.source.DefaultMediaSourceFactory;
import com.google.android.exoplayer2.ui.PlayerView;
import com.google.android.exoplayer2.upstream.DefaultDataSource;
import com.google.android.exoplayer2.upstream.DefaultHttpDataSource;
import com.google.android.exoplayer2.util.Util;

/**
 * SMarTrPlay VideoPlayerActivity — ExoPlayer with HLS/m3u8 support.
 * Launched from MainActivity via JavaScript bridge.
 * Supports D-Pad media keys and auto-hides controls.
 */
public class VideoPlayerActivity extends Activity implements Player.Listener {

    private ExoPlayer player;
    private PlayerView playerView;
    private TextView overlayTitle;
    private String streamUrl;
    private String streamTitle;
    private final Handler handler = new Handler();
    private final Runnable hideControlsRunnable = this::hideSystemUI;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Fullscreen
        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        );
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        // Build layout programmatically
        FrameLayout rootLayout = new FrameLayout(this);
        rootLayout.setLayoutParams(new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ));

        // PlayerView
        playerView = new PlayerView(this);
        playerView.setLayoutParams(new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ));
        rootLayout.addView(playerView);

        // Title overlay
        overlayTitle = new TextView(this);
        FrameLayout.LayoutParams titleParams = new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT,
            FrameLayout.LayoutParams.WRAP_CONTENT
        );
        titleParams.setMargins(48, 48, 48, 48);
        overlayTitle.setLayoutParams(titleParams);
        overlayTitle.setTextSize(18);
        overlayTitle.setTextColor(0xFFFFFFFF);
        overlayTitle.setShadowLayer(4, 0, 0, 0xCC000000);
        overlayTitle.setVisibility(View.GONE);
        rootLayout.addView(overlayTitle);

        setContentView(rootLayout);

        // Get stream info from intent
        Intent intent = getIntent();
        streamUrl = intent.getStringExtra("url");
        streamTitle = intent.getStringExtra("title");

        if (streamUrl == null || streamUrl.isEmpty()) {
            Toast.makeText(this, "No stream URL provided", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        if (streamTitle != null && !streamTitle.isEmpty()) {
            overlayTitle.setText(streamTitle);
            overlayTitle.setVisibility(View.VISIBLE);
            handler.postDelayed(() -> overlayTitle.setVisibility(View.GONE), 5000);
        }

        initializePlayer();
    }

    private void initializePlayer() {
        if (player == null) {
            DefaultHttpDataSource.Factory httpDataSourceFactory = new DefaultHttpDataSource.Factory()
                .setAllowCrossProtocolRedirects(true)
                .setUserAgent("SMarTrPlay/1.0");

            DefaultDataSource.Factory dataSourceFactory = new DefaultDataSource.Factory(
                this,
                httpDataSourceFactory
            );

            player = new ExoPlayer.Builder(this)
                .setMediaSourceFactory(new DefaultMediaSourceFactory(dataSourceFactory))
                .build();

            player.addListener(this);
            playerView.setPlayer(player);
            player.setPlayWhenReady(true);
        }

        MediaItem mediaItem = MediaItem.fromUri(Uri.parse(streamUrl));

        // Check if HLS
        boolean isHls = streamUrl.contains(".m3u8") || streamUrl.contains("m3u8");
        if (isHls) {
            DefaultHttpDataSource.Factory httpFactory = new DefaultHttpDataSource.Factory()
                .setAllowCrossProtocolRedirects(true)
                .setUserAgent("SMarTrPlay/1.0");
            HlsMediaSource.Factory hlsFactory = new HlsMediaSource.Factory(httpFactory);
            MediaSource mediaSource = hlsFactory.createMediaSource(mediaItem);
            player.setMediaSource(mediaSource);
            player.prepare();
        } else {
            player.setMediaItem(mediaItem);
            player.prepare();
        }
    }

    // ===== Player.Listener callbacks =====

    @Override
    public void onPlaybackStateChanged(int state) {
        switch (state) {
            case Player.STATE_READY:
                // Auto-hide controls after playback starts
                handler.postDelayed(hideControlsRunnable, 3000);
                break;
            case Player.STATE_ENDED:
                finish();
                break;
        }
    }

    @Override
    public void onPlayerError(PlaybackException error) {
        String errorMsg = "Playback error: " + (error.getMessage() != null ? error.getMessage() : "unknown");
        Toast.makeText(this, errorMsg, Toast.LENGTH_LONG).show();
        handler.postDelayed(this::finish, 3000);
    }

    // ===== D-Pad / Media Key handling =====

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (player == null) return super.onKeyDown(keyCode, event);

        switch (keyCode) {
            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER:
                if (player.isPlaying()) {
                    player.pause();
                    showSystemUI();
                } else {
                    player.play();
                    hideSystemUI();
                }
                return true;

            case KeyEvent.KEYCODE_DPAD_RIGHT:
                player.seekTo(player.getCurrentPosition() + 10000); // +10s
                return true;

            case KeyEvent.KEYCODE_DPAD_LEFT:
                player.seekTo(player.getCurrentPosition() - 10000); // -10s
                return true;

            case KeyEvent.KEYCODE_DPAD_UP:
                // Increase volume via AudioManager
                return super.onKeyDown(keyCode, event);

            case KeyEvent.KEYCODE_DPAD_DOWN:
                return super.onKeyDown(keyCode, event);

            case KeyEvent.KEYCODE_MEDIA_PLAY:
                player.play();
                return true;

            case KeyEvent.KEYCODE_MEDIA_PAUSE:
                player.pause();
                return true;

            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
                if (player.isPlaying()) {
                    player.pause();
                } else {
                    player.play();
                }
                return true;

            case KeyEvent.KEYCODE_MEDIA_STOP:
                player.stop();
                finish();
                return true;

            case KeyEvent.KEYCODE_MEDIA_NEXT:
                player.seekTo(player.getCurrentPosition() + 30000); // +30s
                return true;

            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
                player.seekTo(player.getCurrentPosition() - 30000); // -30s
                return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    private void hideSystemUI() {
        int uiFlags = View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY;
        getWindow().getDecorView().setSystemUiVisibility(uiFlags);
        if (playerView != null) {
            playerView.hideController();
        }
    }

    private void showSystemUI() {
        if (playerView != null) {
            playerView.showController();
        }
        handler.postDelayed(hideControlsRunnable, 5000);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (player != null) {
            player.setPlayWhenReady(true);
        }
        hideSystemUI();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (player != null) {
            player.setPlayWhenReady(false);
        }
    }

    @Override
    protected void onDestroy() {
        if (player != null) {
            player.removeListener(this);
            player.release();
            player = null;
        }
        super.onDestroy();
    }

    @Override
    public void onUserInteraction() {
        super.onUserInteraction();
        handler.removeCallbacks(hideControlsRunnable);
        handler.postDelayed(hideControlsRunnable, 5000);
    }
}
