function Landing({ onCitizen, onOperator }) {
  return (
    <div className="landing">
      <div className="landing-box">
        <div className="logo">SD</div>

        <h1>SafeDrop AI</h1>
        <p>
          AI kamera monitoringi va fuqarolardan kelgan xabarlarni operator panelida birlashtiruvchi platforma.
        </p>

        <div className="role-grid">
          <button onClick={onCitizen} className="role-button">
            <span>Fuqaro portali</span>
            <strong>Xabar yuborish</strong>
            <p>Anonim yoki ism bilan shubhali holat haqida xabar qoldirish.</p>
          </button>

          <button onClick={onOperator} className="role-button">
            <span>Operator paneli</span>
            <strong>Cybersecurity console</strong>
            <p>AI alertlar va fuqarolar xabarlarini ko‘rib chiqish.</p>
          </button>
        </div>
      </div>
    </div>
  );
}

export default Landing;