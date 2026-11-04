package tui

import (
	tea "charm.land/bubbletea/v2"
	"context"
	"github.com/levyvix/league-auto-accept/internal/config"
	"strings"
	"testing"
)

func TestSettingsAndPicker(t *testing.T) {
	s := config.Defaults()
	s.AutoSave = false
	m := New(context.Background(), s, "unused")
	m.screen = "settings"
	next, _ := m.Update(tea.KeyPressMsg{Code: 'p', Text: "p"})
	m = next.(Model)
	if m.Settings.AutoPick {
		t.Fatal("pick toggle")
	}
	m.screen = "picker"
	m.champions = []Champion{{ID: 90, Name: "Malzahar"}, {ID: 22, Name: "Ashe"}}
	m.input.SetValue("mal")
	if len(m.filtered()) != 2 {
		t.Fatal(m.filtered())
	}
	if !strings.Contains(m.View().Content, "Malzahar") {
		t.Fatal("missing filtered champion")
	}
}
