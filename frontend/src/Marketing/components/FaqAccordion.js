import { useState } from "react";

function FaqAccordion({ items }) {
  const [openIndex, setOpenIndex] = useState(0);

  return (
    <div className="mkt-faq">
      {items.map((item, index) => {
        const isOpen = openIndex === index;
        const panelId = `mkt-faq-panel-${index}`;
        const buttonId = `mkt-faq-button-${index}`;

        return (
          <div key={item.question} className={`mkt-faq__item${isOpen ? " mkt-faq__item--open" : ""}`}>
            <button
              type="button"
              id={buttonId}
              className="mkt-faq__trigger"
              aria-expanded={isOpen}
              aria-controls={panelId}
              onClick={() => setOpenIndex(isOpen ? -1 : index)}
            >
              <span>{item.question}</span>
            </button>
            <div
              id={panelId}
              role="region"
              aria-labelledby={buttonId}
              className="mkt-faq__panel"
              hidden={!isOpen}
            >
              <p>{item.answer}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default FaqAccordion;
