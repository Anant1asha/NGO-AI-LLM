export const config = {
  display: {
    inputStyle: 'block',
    toolDisplay: 'grouped',
    loader: {
      style: 'spinner',
      text: 'Working'
    },
    showBanner: true
  },
  serverTools: [
    { type: 'openrouter:web_search', default: true },
    { type: 'openrouter:datetime', default: true }
  ],
  harness: {
    sessionPersistence: true,
    structuredEventLogging: true,
    autoApproveAll: true // HIL disabled by user request
  }
};
