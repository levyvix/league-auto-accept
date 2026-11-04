package update

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/shirou/gopsutil/v4/process"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const Version = "0.5.0" // x-release-please-version

type Release struct {
	Tag    string `json:"tag_name"`
	URL    string `json:"html_url"`
	Assets []struct {
		Name string `json:"name"`
		URL  string `json:"browser_download_url"`
	} `json:"assets"`
}

func Check(ctx context.Context) (Release, error) {
	var r Release
	req, e := http.NewRequestWithContext(ctx, "GET", "https://api.github.com/repos/levyvix/league-auto-accept/releases/latest", nil)
	if e != nil {
		return r, e
	}
	req.Header.Set("Accept", "application/vnd.github+json")
	client := http.Client{Timeout: 8 * time.Second}
	resp, e := client.Do(req)
	if e != nil {
		return r, e
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return r, fmt.Errorf("release check: HTTP %d", resp.StatusCode)
	}
	e = json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&r)
	return r, e
}
func Stage(ctx context.Context, r Release) (string, error) {
	if !Newer(r.Tag, Version) {
		return "", fmt.Errorf("release is not newer than installed version %s", Version)
	}
	url := ""
	for _, a := range r.Assets {
		if a.Name == "league-auto-accept-go.exe" {
			url = a.URL
			break
		}
	}
	if url == "" {
		return "", fmt.Errorf("release has no native Go executable")
	}
	if !strings.HasPrefix(url, "https://github.com/levyvix/league-auto-accept/releases/download/") {
		return "", fmt.Errorf("unexpected release asset URL")
	}
	req, e := http.NewRequestWithContext(ctx, "GET", url, nil)
	if e != nil {
		return "", e
	}
	client := http.Client{Timeout: 2 * time.Minute}
	resp, e := client.Do(req)
	if e != nil {
		return "", e
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return "", fmt.Errorf("download: HTTP %d", resp.StatusCode)
	}
	f, e := os.CreateTemp("", "league-update-*.exe")
	if e != nil {
		return "", e
	}
	_, e = io.Copy(f, io.LimitReader(resp.Body, 100<<20))
	closeErr := f.Close()
	if e != nil {
		os.Remove(f.Name())
		return "", e
	}
	if closeErr != nil {
		return "", closeErr
	}
	return f.Name(), nil
}

func Newer(tag, current string) bool {
	parse := func(v string) ([3]int, bool) {
		var result [3]int
		v = strings.TrimPrefix(v, "league-auto-accept-v")
		v = strings.TrimPrefix(v, "v")
		parts := strings.Split(v, ".")
		if len(parts) != 3 {
			return result, false
		}
		for i, p := range parts {
			n, err := strconv.Atoi(p)
			if err != nil || n < 0 {
				return result, false
			}
			result[i] = n
		}
		return result, true
	}
	a, ok := parse(tag)
	if !ok {
		return false
	}
	b, ok := parse(current)
	if !ok {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return a[i] > b[i]
		}
	}
	return false
}
func Launch(staged string) error {
	target, e := os.Executable()
	if e != nil {
		return e
	}
	return exec.Command(staged, "--replace", target, "--wait", fmt.Sprint(os.Getpid())).Start()
}
func Replace(target string, pid int) error {
	deadline := time.Now().Add(30 * time.Second)
	for time.Now().Before(deadline) {
		exists, _ := process.PidExists(int32(pid))
		if !exists {
			break
		}
		time.Sleep(200 * time.Millisecond)
	}
	exists, _ := process.PidExists(int32(pid))
	if exists {
		return fmt.Errorf("application did not exit")
	}
	self, e := os.Executable()
	if e != nil {
		return e
	}
	in, e := os.Open(self)
	if e != nil {
		return e
	}
	defer in.Close()
	f, e := os.CreateTemp(filepath.Dir(target), "update-*.exe")
	if e != nil {
		return e
	}
	defer os.Remove(f.Name())
	if _, e = io.Copy(f, in); e != nil {
		f.Close()
		return e
	}
	if e = f.Close(); e != nil {
		return e
	}
	if e = os.Rename(f.Name(), target); e != nil {
		return e
	}
	return exec.Command(target).Start()
}
