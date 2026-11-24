package org.fastdl.mobile;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.widget.*;
import java.util.Locale;

public class MainActivity extends Activity {
 @Override public void onCreate(Bundle state) {
  super.onCreate(state);
  LinearLayout layout = new LinearLayout(this);
  layout.setOrientation(LinearLayout.VERTICAL);
  layout.setPadding(32,64,32,32);
  TextView title = new TextView(this);
  title.setText("Fast HD Downloader — Android Alpha"); title.setTextSize(24);
  layout.addView(title);
  EditText url = new EditText(this);
  url.setHint("Authorized direct HTTPS media URL");
  url.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
  layout.addView(url);
  CheckBox consent = new CheckBox(this);
  consent.setText("I have permission to download this file");
  layout.addView(consent);
  Button button = new Button(this); button.setText("Download"); layout.addView(button);
  TextView status = new TextView(this); layout.addView(status);
  button.setOnClickListener(v -> {
   try {
    if (!consent.isChecked()) throw new IllegalArgumentException("Confirm download permission.");
    java.net.URI parsed = new java.net.URI(url.getText().toString().trim());
    if (!"https".equalsIgnoreCase(parsed.getScheme()) || parsed.getHost()==null || parsed.getUserInfo()!=null)
     throw new IllegalArgumentException("A direct HTTPS URL is required.");
    String path = parsed.getPath();
    String lower = path == null ? "" : path.toLowerCase(Locale.ROOT);
    String ext = "";
    for (String e : new String[]{".mp4",".mp3",".m4a",".webm"}) if (lower.endsWith(e)) ext=e;
    if (ext.isEmpty()) throw new IllegalArgumentException("Direct MP4, MP3, M4A or WebM links only. Video pages and DRM streams are unsupported.");
    DownloadManager.Request req = new DownloadManager.Request(Uri.parse(parsed.toASCIIString()));
    req.setTitle("Fast HD Downloader");
    req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
    req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "FastHD-"+java.util.UUID.randomUUID()+ext);
    long id = ((DownloadManager)getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(req);
    status.setText("Queued: "+id+" — see Android Downloads for progress.");
   } catch (Exception e) { status.setText("Unable to queue: "+e.getMessage()); }
  });
  setContentView(layout);
 }
}
