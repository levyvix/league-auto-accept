package lcu

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestAuthenticatedJSONAndErrors(t *testing.T) {
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		u, p, ok := r.BasicAuth()
		if !ok || u != "riot" || p != "secret" {
			t.Error("missing authentication")
		}
		if r.URL.Path == "/failure" {
			w.WriteHeader(409)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"phase":"Lobby"}`))
	}))
	defer server.Close()
	c := New("1", "secret")
	c.URL = server.URL
	var out struct{ Phase string }
	if err := c.Request(context.Background(), "GET", "session", nil, &out); err != nil || out.Phase != "Lobby" {
		t.Fatal(err, out)
	}
	if err := c.Request(context.Background(), "PATCH", "failure", map[string]int{"championId": 1}, nil); err == nil {
		t.Fatal("expected HTTP failure")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := c.Request(ctx, "GET", "session", nil, nil); err == nil {
		t.Fatal("expected cancellation")
	}
}
