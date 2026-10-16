package android.view;
public class View {
    public View(android.content.Context c) {}
    public void setBackgroundColor(int c) {}
    public void setPadding(int l, int t, int r, int b) {}
    public void setClickable(boolean b) {}
    public void setOnClickListener(OnClickListener l) {}
    public interface OnClickListener { void onClick(View v); }
}
