package update

import "testing"

func TestOnlyNewerStableReleases(t *testing.T) {
	for _, tt := range []struct {
		tag  string
		want bool
	}{{"league-auto-accept-v0.6.0", true}, {"v0.5.1", true}, {"0.5.0", false}, {"0.4.9", false}, {"bad", false}, {"0.6.0-rc1", false}} {
		if got := Newer(tt.tag, "0.5.0"); got != tt.want {
			t.Errorf("%s: %v", tt.tag, got)
		}
	}
}
