(() => {
  const storagePrefix = "omicshub:table-widths:";
  const minimumWidth = 96;

  const readWidths = (tableName) => {
    try {
      return JSON.parse(localStorage.getItem(storagePrefix + tableName) || "{}");
    } catch {
      return {};
    }
  };

  const saveWidths = (tableName, widths) => {
    try {
      localStorage.setItem(storagePrefix + tableName, JSON.stringify(widths));
    } catch {
      return;
    }
  };

  document.querySelectorAll("[data-resizable-table]").forEach((table) => {
    const tableName = table.dataset.resizableTable;
    const columns = new Map(
      [...table.querySelectorAll("col[data-column-key]")].map((column) => [column.dataset.columnKey, column]),
    );
    const lastColumn = [...columns.values()].at(-1);
    const minimumTableWidth = table.parentElement.clientWidth;
    const widths = readWidths(tableName);
    const initialWidths = new Map(
      [...table.querySelectorAll("col")].map((column) => [column, column.getBoundingClientRect().width]),
    );
    let tableWidth;

    table.querySelectorAll("col").forEach((column) => {
      const key = column.dataset.columnKey;
      const savedWidth = key && widths[key];
      const width = savedWidth ? Math.max(minimumWidth, savedWidth) : initialWidths.get(column);
      column.style.width = `${width}px`;
    });
    tableWidth = [...table.querySelectorAll("col")].reduce(
      (total, column) => total + Number.parseFloat(column.style.width),
      0,
    );
    if (lastColumn && tableWidth < minimumTableWidth) {
      lastColumn.style.width = `${Number.parseFloat(lastColumn.style.width) + minimumTableWidth - tableWidth}px`;
      tableWidth = minimumTableWidth;
    }
    table.style.tableLayout = "fixed";
    table.style.width = `${tableWidth}px`;

    table.querySelectorAll("th[data-column-key]").forEach((header) => {
      const key = header.dataset.columnKey;
      const column = columns.get(key);
      if (!column) return;

      const handle = document.createElement("button");
      handle.type = "button";
      handle.className = "column-resize-handle";
      const label = header.textContent.trim();
      handle.setAttribute("aria-label", `Resize ${label} column`);
      handle.title = `Drag to resize ${label} column`;
      header.append(handle);

      const setWidth = (width) => {
        const currentWidth = column.getBoundingClientRect().width;
        let nextWidth = Math.max(minimumWidth, Math.round(width));
        const nextTableWidth = tableWidth + nextWidth - currentWidth;
        if (column === lastColumn && nextTableWidth < minimumTableWidth) {
          nextWidth += minimumTableWidth - nextTableWidth;
        }
        column.style.width = `${nextWidth}px`;
        tableWidth += nextWidth - currentWidth;
        table.style.width = `${tableWidth}px`;
        widths[key] = nextWidth;
      };

      const adjust = (amount) => {
        setWidth(column.getBoundingClientRect().width + amount);
        saveWidths(tableName, widths);
      };

      handle.addEventListener("keydown", (event) => {
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
          event.preventDefault();
          adjust(event.key === "ArrowLeft" ? -16 : 16);
        }
      });

      handle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        const startX = event.clientX;
        const startWidth = column.getBoundingClientRect().width;
        document.documentElement.classList.add("is-resizing-columns");

        const move = (moveEvent) => setWidth(startWidth + moveEvent.clientX - startX);
        const stop = () => {
          document.removeEventListener("pointermove", move);
          document.removeEventListener("pointerup", stop);
          document.removeEventListener("pointercancel", stop);
          document.documentElement.classList.remove("is-resizing-columns");
          saveWidths(tableName, widths);
        };

        document.addEventListener("pointermove", move);
        document.addEventListener("pointerup", stop, { once: true });
        document.addEventListener("pointercancel", stop, { once: true });
      });
    });
  });
})();
