### 📌 Main **Network events** you’ll see in `performance` logs or via DevTools listeners

* **Request lifecycle**

  * `Network.requestWillBeSent` — a request is about to be sent (first point you can see URL, headers).
  * `Network.requestWillBeSentExtraInfo` — extra headers info (sometimes split for security reasons).
  * `Network.requestServedFromCache` — request was fulfilled from browser cache.

* **Response lifecycle**

  * `Network.responseReceived` — headers/status arrived.
  * `Network.responseReceivedExtraInfo` — extra response header info.
  * `Network.dataReceived` — chunk of response data received.
  * `Network.loadingFinished` — all response data is received.
  * `Network.loadingFailed` — request failed (with reason).

* **WebSocket / EventSource**

  * `Network.webSocketCreated`
  * `Network.webSocketWillSendHandshakeRequest`
  * `Network.webSocketHandshakeResponseReceived`
  * `Network.webSocketFrameSent`
  * `Network.webSocketFrameReceived`
  * `Network.webSocketClosed`
  * `Network.webSocketFrameError`

* **Other network activity**

  * `Network.webTransportCreated`, `Network.webTransportClosed`
  * `Network.eventSourceMessageReceived`
  * `Network.signedExchangeReceived`
  * `Network.subresourceWebBundleMetadataReceived`
  * `Network.subresourceWebBundleMetadataError`
  * `Network.subresourceWebBundleInnerResponseParsed`
  * `Network.reportingApiReportAdded`, `Network.reportingApiReportUpdated`, `Network.reportingApiEndpointsChanged`

---

### 📌 Main **Network commands** (things you can call via CDP)

Examples:

* `Network.enable`, `Network.disable`
* `Network.getResponseBody`
* `Network.setExtraHTTPHeaders`
* `Network.setUserAgentOverride`
* `Network.emulateNetworkConditions`
* `Network.clearBrowserCache`, `Network.clearBrowserCookies`
* `Network.setBlockedURLs`
* `Network.getCookies`, `Network.setCookie`, `Network.deleteCookies`
```
