package lcu

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"github.com/shirou/gopsutil/v4/process"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"
)

type API interface {
	Request(context.Context, string, string, any, any) error
}
type Client struct {
	URL, token string
	HTTP       *http.Client
}

func New(port, token string) *Client {
	return &Client{URL: "https://127.0.0.1:" + port, token: token, HTTP: &http.Client{Timeout: 5 * time.Second, Transport: &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}}}
}
func (c *Client) Request(ctx context.Context, method, path string, body, out any) error {
	var data []byte
	var e error
	if body != nil {
		data, e = json.Marshal(body)
		if e != nil {
			return e
		}
	}
	r, e := http.NewRequestWithContext(ctx, method, c.URL+"/"+strings.TrimPrefix(path, "/"), bytes.NewReader(data))
	if e != nil {
		return e
	}
	r.SetBasicAuth("riot", c.token)
	r.Header.Set("Content-Type", "application/json")
	resp, e := c.HTTP.Do(r)
	if e != nil {
		return fmt.Errorf("LCU unavailable: %w", e)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("LCU %s %s: HTTP %d", method, path, resp.StatusCode)
	}
	if out == nil {
		_, e = io.Copy(io.Discard, resp.Body)
		return e
	}
	return json.NewDecoder(io.LimitReader(resp.Body, 8<<20)).Decode(out)
}

var portPattern = regexp.MustCompile(`--app-port="?([0-9]+)`)
var tokenPattern = regexp.MustCompile(`--remoting-auth-token="?([a-zA-Z0-9_-]+)`)

func Discover(ctx context.Context) (*Client, error) {
	ps, e := process.ProcessesWithContext(ctx)
	if e != nil {
		return nil, e
	}
	for _, p := range ps {
		name, e := p.NameWithContext(ctx)
		if e != nil || !strings.EqualFold(name, "LeagueClientUx.exe") {
			continue
		}
		args, e := p.CmdlineWithContext(ctx)
		if e != nil {
			continue
		}
		port, token := portPattern.FindStringSubmatch(args), tokenPattern.FindStringSubmatch(args)
		if len(port) > 1 && len(token) > 1 {
			return New(port[1], token[1]), nil
		}
	}
	return nil, fmt.Errorf("waiting for League Client")
}
