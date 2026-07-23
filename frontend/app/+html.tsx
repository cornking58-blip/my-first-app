// @ts-nocheck
import { ScrollViewStyleReset } from "expo-router/html";
import type { PropsWithChildren } from "react";

export default function Root({ children }: PropsWithChildren) {
  return (
    <html lang="en" style={{ height: "100%" }}>
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, shrink-to-fit=no"
        />
        {/*
          Disable body scrolling on web to make ScrollView components work correctly.
          If you want to enable scrolling, remove `ScrollViewStyleReset` and
          set `overflow: auto` on the body style below.
        */}
        <ScrollViewStyleReset />
        <style
          dangerouslySetInnerHTML={{
            __html: `
              body > div:first-child { position: fixed !important; top: 0; left: 0; right: 0; bottom: 0; }
              [role="tablist"] [role="tab"] * { overflow: visible !important; }
              [role="heading"], [role="heading"] * { overflow: visible !important; }
              [data-testid="main-search-input"] {
                appearance: none !important;
                -webkit-appearance: none !important;
                background-color: transparent !important;
                color: #F7F7FC !important;
                outline: none !important;
                border: 0 !important;
                box-shadow: none !important;
                -webkit-text-fill-color: #F7F7FC !important;
                caret-color: #9D82FF !important;
              }
              [data-testid="main-search-input"]:focus,
              [data-testid="main-search-input"]:focus-visible {
                background-color: transparent !important;
                outline: none !important;
                box-shadow: none !important;
              }
              [data-testid="main-search-input"]::selection {
                background-color: #604BB3;
                color: #FFFFFF;
              }
              [data-testid="main-search-input"]:-webkit-autofill,
              [data-testid="main-search-input"]:-webkit-autofill:hover,
              [data-testid="main-search-input"]:-webkit-autofill:focus {
                -webkit-text-fill-color: #F7F7FC !important;
                -webkit-box-shadow: 0 0 0 1000px #202B59 inset !important;
                box-shadow: 0 0 0 1000px #202B59 inset !important;
              }
            `,
          }}
        />
      </head>
      <body
        style={{
          margin: 0,
          height: "100%",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {children}
      </body>
    </html>
  );
}
