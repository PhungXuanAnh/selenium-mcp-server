// Preloaded only into Chrome launched by selenium-mcp-server. The system title bar sends
// WM_DELETE_WINDOW for X/Alt+F4; a browser window of this process is hidden instead of closed.
// The same library is loaded by the tray daemon to list and restore hidden windows.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <xcb/xcb.h>

#define EXPORT __attribute__((visibility("default")))
#define BROWSER_ROLE "browser"

typedef struct {
  xcb_connection_t *connection;
  xcb_window_t root;
  xcb_atom_t protocols, delete_window, pid, role, window_type, normal, hidden, saved_state;
  xcb_atom_t state, state_hidden, state_focused, active_window, close_window, name, utf8;
} Control;

static xcb_atom_t atom(xcb_connection_t *c, const char *name) {
  xcb_intern_atom_reply_t *reply = xcb_intern_atom_reply(
      c, xcb_intern_atom(c, 0, strlen(name), name), NULL);
  xcb_atom_t value = reply ? reply->atom : XCB_ATOM_NONE;
  free(reply);
  return value;
}

static int open_control(Control *control) {
  xcb_connection_t *c = control->connection = xcb_connect(NULL, NULL);
  if (xcb_connection_has_error(c)) {
    xcb_disconnect(c);
    control->connection = NULL;
    return 0;
  }
  control->root = xcb_setup_roots_iterator(xcb_get_setup(c)).data->root;
  control->protocols = atom(c, "WM_PROTOCOLS");
  control->delete_window = atom(c, "WM_DELETE_WINDOW");
  control->pid = atom(c, "_NET_WM_PID");
  control->role = atom(c, "WM_WINDOW_ROLE");
  control->window_type = atom(c, "_NET_WM_WINDOW_TYPE");
  control->normal = atom(c, "_NET_WM_WINDOW_TYPE_NORMAL");
  control->hidden = atom(c, "_SELENIUM_MCP_HIDDEN");
  control->saved_state = atom(c, "_SELENIUM_MCP_SAVED_STATE");
  control->state = atom(c, "_NET_WM_STATE");
  control->state_hidden = atom(c, "_NET_WM_STATE_HIDDEN");
  control->state_focused = atom(c, "_NET_WM_STATE_FOCUSED");
  control->active_window = atom(c, "_NET_ACTIVE_WINDOW");
  control->close_window = atom(c, "_NET_CLOSE_WINDOW");
  control->name = atom(c, "_NET_WM_NAME");
  control->utf8 = atom(c, "UTF8_STRING");
  return 1;
}

static xcb_get_property_reply_t *property(Control *control, xcb_window_t window,
                                          xcb_atom_t name, xcb_atom_t type) {
  return xcb_get_property_reply(control->connection,
      xcb_get_property(control->connection, 0, window, name, type, 0, 1024), NULL);
}

static uint32_t cardinal(Control *control, xcb_window_t window, xcb_atom_t name) {
  xcb_get_property_reply_t *reply = property(control, window, name, XCB_ATOM_CARDINAL);
  uint32_t value = 0;
  if (reply && reply->format == 32 && xcb_get_property_value_length(reply) == 4)
    value = *(uint32_t *)xcb_get_property_value(reply);
  free(reply);
  return value;
}

// Tabbed browser windows only: DevTools, pop-ups and native dialogs keep their normal close.
static int browser_window(Control *control, xcb_window_t window) {
  xcb_get_property_reply_t *reply = property(control, window, control->role, XCB_ATOM_STRING);
  int matches = reply && reply->format == 8
      && xcb_get_property_value_length(reply) == (int)strlen(BROWSER_ROLE)
      && !memcmp(xcb_get_property_value(reply), BROWSER_ROLE, strlen(BROWSER_ROLE));
  free(reply);
  if (!matches) return 0;
  reply = property(control, window, control->window_type, XCB_ATOM_ATOM);
  matches = reply && reply->format == 32 && xcb_get_property_value_length(reply) >= 4
      && *(xcb_atom_t *)xcb_get_property_value(reply) == control->normal;
  free(reply);
  return matches;
}

static void hide_window(Control *control, xcb_window_t window) {
  xcb_connection_t *c = control->connection;
  // A withdrawn window loses its WM state; keep maximized/fullscreen/above for the restore.
  xcb_get_property_reply_t *reply = property(control, window, control->state, XCB_ATOM_ATOM);
  xcb_atom_t saved[64];
  unsigned count = 0;
  if (reply && reply->format == 32) {
    xcb_atom_t *states = xcb_get_property_value(reply);
    unsigned length = xcb_get_property_value_length(reply) / sizeof(xcb_atom_t);
    for (unsigned i = 0; i < length && count < 64; ++i) {
      if (states[i] != control->state_hidden && states[i] != control->state_focused)
        saved[count++] = states[i];
    }
  }
  free(reply);
  xcb_change_property(c, XCB_PROP_MODE_REPLACE, window, control->saved_state, XCB_ATOM_ATOM, 32, count, saved);
  uint32_t pid = getpid();
  xcb_change_property(c, XCB_PROP_MODE_REPLACE, window, control->hidden, XCB_ATOM_CARDINAL, 32, 1, &pid);
  xcb_unmap_window(c, window);
  xcb_flush(c);
}

static int intercept(xcb_generic_event_t *event) {
  if ((event->response_type & 127) != XCB_CLIENT_MESSAGE) return 0;
  xcb_client_message_event_t *message = (void *)event;
  if (message->format != 32) return 0;
  // Never send requests on Chrome's own XCB connection: its request sequence accounting
  // would break. Each polling thread keeps a separate control connection.
  static _Thread_local Control control;
  if (!control.connection && !open_control(&control)) return 0;
  if (message->type != control.protocols || message->data.data32[0] != control.delete_window) return 0;
  if (cardinal(&control, message->window, control.pid) != (uint32_t)getpid()
      || !browser_window(&control, message->window)) return 0;
  hide_window(&control, message->window);
  return 1;
}

#define WRAP_POLL(name) \
  EXPORT xcb_generic_event_t *name(xcb_connection_t *connection) { \
    static _Thread_local xcb_generic_event_t *(*next)(xcb_connection_t *); \
    if (!next) next = dlsym(RTLD_NEXT, #name); \
    if (!next) return NULL; \
    xcb_generic_event_t *event; \
    while ((event = next(connection)) && intercept(event)) free(event); \
    return event; \
  }
WRAP_POLL(xcb_poll_for_event)
WRAP_POLL(xcb_poll_for_queued_event)
WRAP_POLL(xcb_wait_for_event)

static void finish(Control *control) {
  // Wait until the server processed our requests before closing the short-lived connection.
  free(xcb_get_input_focus_reply(control->connection, xcb_get_input_focus(control->connection), NULL));
  xcb_disconnect(control->connection);
}

static int collect_hidden(Control *control, xcb_window_t parent, unsigned depth,
                          uint32_t *windows, uint32_t *pids, int count, int capacity) {
  xcb_query_tree_reply_t *tree = xcb_query_tree_reply(
      control->connection, xcb_query_tree(control->connection, parent), NULL);
  if (!tree) return count;
  xcb_window_t *children = xcb_query_tree_children(tree);
  for (int i = 0; i < xcb_query_tree_children_length(tree) && count < capacity; ++i) {
    uint32_t pid = cardinal(control, children[i], control->hidden);
    if (pid) {
      windows[count] = children[i];
      pids[count] = pid;
      ++count;
    } else if (depth) {
      // The window manager may not have unparented a just-hidden window from its frame yet.
      count = collect_hidden(control, children[i], depth - 1, windows, pids, count, capacity);
    }
  }
  free(tree);
  return count;
}

// Fills hidden browser windows and their Chrome PIDs; returns the count, or -1 without a display.
EXPORT int selenium_mcp_hidden_windows(uint32_t *windows, uint32_t *pids, int capacity) {
  Control control = {0};
  if (!open_control(&control)) return -1;
  int count = collect_hidden(&control, control.root, 1, windows, pids, 0, capacity);
  xcb_disconnect(control.connection);
  return count;
}

// Copies the UTF-8 window title, NUL-terminated; returns its length, or -1 without a display.
EXPORT int selenium_mcp_window_title(uint32_t window, char *buffer, int capacity) {
  Control control = {0};
  if (!open_control(&control)) return -1;
  xcb_get_property_reply_t *reply = property(&control, window, control.name, control.utf8);
  int length = 0;
  if (reply && reply->format == 8) {
    length = xcb_get_property_value_length(reply);
    if (length > capacity - 1) length = capacity - 1;
    memcpy(buffer, xcb_get_property_value(reply), length);
  }
  buffer[length] = '\0';
  free(reply);
  xcb_disconnect(control.connection);
  return length;
}

// Maps a hidden window again with its saved state and activates it; returns 1 when restored.
EXPORT int selenium_mcp_restore(uint32_t window) {
  Control control = {0};
  if (!open_control(&control)) return -1;
  xcb_connection_t *c = control.connection;
  if (!cardinal(&control, window, control.hidden)) {
    xcb_disconnect(c);
    return 0;
  }
  xcb_get_property_reply_t *saved = property(&control, window, control.saved_state, XCB_ATOM_ATOM);
  if (saved && saved->format == 32) {
    xcb_change_property(c, XCB_PROP_MODE_REPLACE, window, control.state, XCB_ATOM_ATOM,
                        32, xcb_get_property_value_length(saved) / 4, xcb_get_property_value(saved));
  }
  free(saved);
  xcb_delete_property(c, window, control.saved_state);
  xcb_delete_property(c, window, control.hidden);
  xcb_map_window(c, window);
  xcb_client_message_event_t activate = {0};
  activate.response_type = XCB_CLIENT_MESSAGE;
  activate.format = 32;
  activate.window = window;
  activate.type = control.active_window;
  activate.data.data32[0] = 2;  // Source indication: an explicit user/tray action.
  xcb_send_event(c, 0, control.root,
                 XCB_EVENT_MASK_SUBSTRUCTURE_REDIRECT | XCB_EVENT_MASK_SUBSTRUCTURE_NOTIFY,
                 (const char *)&activate);
  finish(&control);
  return 1;
}

// Asks the window manager to close a window, exactly like its title-bar X button.
EXPORT int selenium_mcp_request_close(uint32_t window) {
  Control control = {0};
  if (!open_control(&control)) return -1;
  xcb_client_message_event_t close = {0};
  close.response_type = XCB_CLIENT_MESSAGE;
  close.format = 32;
  close.window = window;
  close.type = control.close_window;
  close.data.data32[1] = 2;  // Source indication: an explicit user action.
  xcb_send_event(control.connection, 0, control.root,
                 XCB_EVENT_MASK_SUBSTRUCTURE_REDIRECT | XCB_EVENT_MASK_SUBSTRUCTURE_NOTIFY,
                 (const char *)&close);
  finish(&control);
  return 1;
}
