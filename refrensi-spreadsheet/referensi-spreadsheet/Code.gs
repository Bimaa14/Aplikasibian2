
//function file transaction to change location sheet
  function totransaction() {
  pindahSheet("TRANSACTION");
 }

  function todatabase() {
  pindahSheet("DATABASE");
 }

  function tosellingcash() {
    pindahSheet("SELLING CASH");
  }

  function tosellingcredit() {
    pindahSheet("SELLING CREDIT");
  }

  function tosellingoil() {
    pindahSheet("SELLING OIL");
  }

  function topurchase() {
    pindahSheet("PURCHASE");
  }

  function topaymentcredit() {
    pindahSheet("PAYMENT CREDIT");
  }

  function tocashout() {
    pindahSheet("EXPENSES");
  }

  function toreport() {
    pindahSheet("DAILY REPORT");
  }


// MAIN FUCTION
  function pindahSheet(namaSheet) {
    var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    var targetSheet = spreadsheet.getSheetByName(namaSheet);
    
    if (targetSheet) {
      spreadsheet.setActiveSheet(targetSheet);
    } else {
      SpreadsheetApp.getUi().alert("Sheet '" + namaSheet + "' tidak ditemukan!");
    }
  }




// functions to save field to database sheet
// function to add item
  function additem() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("DATABASE");


    var size = Shtinput.getRange('E6').getValue();
    var tipe = Shtinput.getRange('E8').getValue();
    var brand = Shtinput.getRange('E10').getValue();
    var stock = Shtinput.getRange('E12').getValue();
    var sellingprice = Shtinput.getRange('E14').getValue();
    var costprice = Shtinput.getRange('E16').getValue();
    var who = Shtinput.getRange('E18').getValue();
    var tax = Shtinput.getRange('E20').getValue();
    var servicefee = Shtinput.getRange('E22').getValue();
    var category = Shtinput.getRange('E24').getValue();
    
    var row = Shtdb.getRange('R1').getValue();
    row += 1;
    var rangefield = Shtdb.getRange('D' + row + ":M" + row);
    rangefield.setValues([[size, tipe, brand, stock,sellingprice,costprice,who,tax,servicefee,category]]);
    clear1()
  }

  function clear1() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('E6').clearContent();
    Shtinput.getRange('E8').clearContent();
    Shtinput.getRange('E10').clearContent();
    Shtinput.getRange('E12').clearContent();
    Shtinput.getRange('E14').clearContent();
    Shtinput.getRange('E16').clearContent();
    Shtinput.getRange('E18').clearContent();
    Shtinput.getRange('E20').clearContent();
    Shtinput.getRange('E22').clearContent();
    Shtinput.getRange('E24').clearContent();
    Shtinput.getRange('E26').clearContent();
  }

// function to add customer
  function addcust() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("DATABASE");

    var code = Shtinput.getRange('E38').getValue();
    var name = Shtinput.getRange('E40').getValue();

    var row = Shtdb.getRange('AA1').getValue();
    row+=1;
    var rangefield = Shtdb.getRange('V' + row + ":W" + row);
    rangefield.setValues([[code, name]]);
    clear2()
  }
  function clear2() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('E40').clearContent();
  }

// function to add distributor
  function adddistributor() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("DATABASE");

    var code = Shtinput.getRange('E68').getValue();
    var name = Shtinput.getRange('E70').getValue();

    var row = Shtdb.getRange('AJ1').getValue();
    row+=1;
    var rangefield = Shtdb.getRange('AD' + row + ":AE" + row);
    rangefield.setValues([[code, name]]);
    clear3()
  }
  function clear3() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('E70').clearContent();
  }

// function to add selling
  function addselling() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("SELLING CASH");


    var date = Shtinput.getRange('K6').getValue();
    var invoice = Shtinput.getRange('K8').getValue();
    var item = Shtinput.getRange('K10').getValue();
    var qty = Shtinput.getRange('K12').getValue();
    var price = Shtinput.getRange('K14').getValue();
    var discon = Shtinput.getRange('K16').getValue();
    
    var row = Shtdb.getRange('S1').getValue();
    row += 1;
    var rangefield = Shtdb.getRange('C' + row + ":H" + row);
    rangefield.setValues([[date, invoice,item,qty,price,discon]]);
    clear4()
  }

  function clear4() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('K10').clearContent();
    Shtinput.getRange('K12').clearContent();
    Shtinput.getRange('K16').clearContent();
  }

// function to save selling
  function saveselling() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("SELLING CASH");


    var date = Shtinput.getRange('K6').getValue();
    var invoice = Shtinput.getRange('K8').getValue();
    var item = Shtinput.getRange('K10').getValue();
    var qty = Shtinput.getRange('K12').getValue();
    var price = Shtinput.getRange('K14').getValue();
    var discon = Shtinput.getRange('K16').getValue();
    
    var row = Shtdb.getRange('S1').getValue();
    row += 1;
    var rangefield = Shtdb.getRange('C' + row + ":H" + row);
    rangefield.setValues([[date, invoice,item,qty,price,discon]]);
    clear5()
  }

  function clear5() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('K8').clearContent();
    Shtinput.getRange('K10').clearContent();
    Shtinput.getRange('K12').clearContent();
    Shtinput.getRange('K16').clearContent();
  }

// function to add selling credit
  function addsellingcredit() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("SELLING CREDIT");


    var date = Shtinput.getRange('K38').getValue();
    var invoice = Shtinput.getRange('K40').getValue();
    var customer = Shtinput.getRange('K42').getValue();
    var item = Shtinput.getRange('K44').getValue();
    var qty = Shtinput.getRange('K46').getValue();
    var cashprice = Shtinput.getRange('K48').getValue();
    var crediprice = Shtinput.getRange('K50').getValue();
    var duedate = Shtinput.getRange('K52').getValue();

    var row = Shtdb.getRange('U1').getValue();
    row += 1;
    var rangefield = Shtdb.getRange('C' + row + ":J" + row);
    rangefield.setValues([[date,invoice,customer,item,qty,cashprice,crediprice,duedate]]);
    clear6()
  }

  function clear6() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('K44').clearContent();
    Shtinput.getRange('K46').clearContent();
    Shtinput.getRange('K48').clearContent();
    Shtinput.getRange('k50').clearContent();
  }

// function to save selling credit
  function savesellingcredit() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("SELLING CREDIT");


    var date = Shtinput.getRange('K38').getValue();
    var invoice = Shtinput.getRange('K40').getValue();
    var customer = Shtinput.getRange('K42').getValue();
    var item = Shtinput.getRange('K44').getValue();
    var qty = Shtinput.getRange('K46').getValue();
    var cashprice = Shtinput.getRange('K48').getValue();
    var crediprice = Shtinput.getRange('K50').getValue();
    var duedate = Shtinput.getRange('K52').getValue();

    var row = Shtdb.getRange('U1').getValue();
    row += 1;
    var rangefield = Shtdb.getRange('C' + row + ":J" + row);
    rangefield.setValues([[date,invoice,customer,item,qty,cashprice,crediprice,duedate]]);
    clear7()
  }

  function clear7() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('K40').clearContent();
    Shtinput.getRange('K42').clearContent();
    Shtinput.getRange('K44').clearContent();
    Shtinput.getRange('K46').clearContent();
    Shtinput.getRange('K48').clearContent();
    Shtinput.getRange('k50').clearContent();
  }

// function to add purchase
  function addpurchase() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("PURCHASE");


    var date = Shtinput.getRange('Q6').getValue();
    var dateinvoice = Shtinput.getRange('Q8').getValue();
    var distributor = Shtinput.getRange('Q10').getValue();
    var tax = Shtinput.getRange('Q12').getValue();
    var invoice = Shtinput.getRange('Q14').getValue();
    var ownedby = Shtinput.getRange('Q16').getValue();
    var item = Shtinput.getRange('Q18').getValue();
    var qty = Shtinput.getRange('Q20').getValue();
    var price = Shtinput.getRange('Q22').getValue();
    var fixedprice = Shtinput.getRange('Q24').getValue();
    var payment = Shtinput.getRange('Q26').getValue();

    var row = Shtdb.getRange('R1').getValue();
    row += 1;
    var rangefield = Shtdb.getRange('C' + row + ":M" + row);
    rangefield.setValues([[date,dateinvoice,distributor,tax,invoice,ownedby,item,qty,price,fixedprice,payment]]);
    clear8()
  }

  function clear8() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('Q18').clearContent();
    Shtinput.getRange('Q20').clearContent();
    Shtinput.getRange('Q24').clearContent();
  }

// function to save purchase
  function savepurchase() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("PURCHASE");


    var date = Shtinput.getRange('Q6').getValue();
    var dateinvoice = Shtinput.getRange('Q8').getValue();
    var distributor = Shtinput.getRange('Q10').getValue();
    var tax = Shtinput.getRange('Q12').getValue();
    var invoice = Shtinput.getRange('Q14').getValue();
    var ownedby = Shtinput.getRange('Q16').getValue();
    var item = Shtinput.getRange('Q18').getValue();
    var qty = Shtinput.getRange('Q20').getValue();
    var price = Shtinput.getRange('Q22').getValue();
    var fixedprice = Shtinput.getRange('Q24').getValue();
    var payment = Shtinput.getRange('Q26').getValue();

    var row = Shtdb.getRange('R1').getValue();
    row += 1;
    var rangefield = Shtdb.getRange('C' + row + ":M" + row);
    rangefield.setValues([[date,dateinvoice,distributor,tax,invoice,ownedby,item,qty,price,fixedprice,payment]]);
    clear9()
  }

  function clear9() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('Q10').clearContent();
    Shtinput.getRange('Q12').clearContent();
    Shtinput.getRange('Q14').clearContent();
    Shtinput.getRange('Q16').clearContent();
    Shtinput.getRange('Q18').clearContent();
    Shtinput.getRange('Q20').clearContent();
    Shtinput.getRange('Q24').clearContent();
    Shtinput.getRange('Q26').clearContent();
  }

// fuction to save payment to supplier/distributor
  function savepayment() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("PAYMENT SUPPLIER");


  
    var date = Shtinput.getRange('Q38').getValue();
    var name = Shtinput.getRange('Q40').getValue();
    var amount = Shtinput.getRange('Q42').getValue();

    var row = Shtdb.getRange('F1').getValue();
    row += 1;
    var rangefield = Shtdb.getRange('C' + row + ":E" + row);
    rangefield.setValues([[date,name,amount]]);
    clear10()
  }

  function clear10() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('Q40').clearContent();
    Shtinput.getRange('Q42').clearContent();
  }

// Function to save Payment of Receivables
  function paymentcredit(){
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("PAYMENT CREDIT");    

    var datein = Shtinput.getRange('W6').getValue();
    var dateinvoice = Shtinput.getRange('W8').getValue();
    var name = Shtinput.getRange('W10').getValue();
    var amount = Shtinput.getRange('W12').getValue();
    var profit = Shtinput.getRange('W14').getValue();

    var row = Shtdb.getRange('H1').getValue();
    row+=1
    var rangefield = Shtdb.getRange('C' + row + ":G" + row);
    rangefield.setValues([[datein, dateinvoice, name, amount, profit]]);
    clear11()
  }
  function clear11() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('W10').clearContent();
    Shtinput.getRange('W12').clearContent();
  }

// Function to save expenses
  function saveexpenses(){
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("EXPENSES");    

    var date = Shtinput.getRange('W38').getValue();
    var amount = Shtinput.getRange('W40').getValue();
    var explain = Shtinput.getRange('W42').getValue();
    var category = Shtinput.getRange('W44').getValue();
    var payment = Shtinput.getRange('W46').getValue();

    var row = Shtdb.getRange('H1').getValue();
    row+=1
    var rangefield = Shtdb.getRange('C' + row + ":G" + row);
    rangefield.setValues([[date, amount, explain, category, payment]]);
    clear12()
  }
  function clear12() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('W40').clearContent();
    Shtinput.getRange('W42').clearContent();
    Shtinput.getRange('W44').clearContent();
    Shtinput.getRange('W46').clearContent();
  }

// Function to save transfer
  function savetransfer(){
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("TRANSFER");    

    var date = Shtinput.getRange('K68').getValue();
    var amount = Shtinput.getRange('K70').getValue();
    var via = Shtinput.getRange('K72').getValue();
  

    var row = Shtdb.getRange('F2').getValue();
    row+=1
    var rangefield = Shtdb.getRange('C' + row + ":E" + row);
    rangefield.setValues([[date, amount, via]]);
    clear13()
  }
  function clear13() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('K70').clearContent();
    Shtinput.getRange('K72').clearContent();

  }

// Function to add Payment of Receivables
  function addpaymentcredit(){
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("PAYMENT CREDIT");    

    var datein = Shtinput.getRange('W6').getValue();
    var dateinvoice = Shtinput.getRange('W8').getValue();
    var name = Shtinput.getRange('W10').getValue();
    var amount = Shtinput.getRange('W12').getValue();
    var profit = Shtinput.getRange('W14').getValue();

    var row = Shtdb.getRange('H1').getValue();
    row+=1
    var rangefield = Shtdb.getRange('C' + row + ":G" + row);
    rangefield.setValues([[datein, dateinvoice, name, amount, profit]]);
    clear14()
  }
  function clear14() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('W12').clearContent();
  }

// Function to save expenses
  function saveexpenses(){
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");
    var Shtdb = Sheet.getSheetByName("EXPENSES");    

    var date = Shtinput.getRange('W38').getValue();
    var amount = Shtinput.getRange('W40').getValue();
    var explain = Shtinput.getRange('W42').getValue();
    var category = Shtinput.getRange('W44').getValue();
    var payment = Shtinput.getRange('W46').getValue();

    var row = Shtdb.getRange('H1').getValue();
    row+=1
    var rangefield = Shtdb.getRange('C' + row + ":G" + row);
    rangefield.setValues([[date, amount, explain, category, payment]]);
    clear12()
  }
  function clear12() {
    var Sheet = SpreadsheetApp.getActiveSpreadsheet();
    var Shtinput = Sheet.getSheetByName("TRANSACTION");

    Shtinput.getRange('W40').clearContent();
    Shtinput.getRange('W42').clearContent();
    Shtinput.getRange('W44').clearContent();
    Shtinput.getRange('W46').clearContent();
  }

// FUNCTION TO GENERATE DATE Report
  function generateTanggalBulan() {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getActiveSheet();
    
    // Ambil nilai dari M2
    var bulanFilter = sheet.getRange("M2").getValue();
    
    if (!bulanFilter) {
      sheet.getRange("L6:L").clearContent();
      return;
    }
    
    try {
      // Mapping nama bulan ke angka
      var bulanMap = {
        "Januari": 1, "Februari": 2, "Maret": 3, "April": 4, 
        "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8, 
        "September": 9, "Oktober": 10, "November": 11, "Desember": 12
      };
      
      var bulanAngka = bulanMap[bulanFilter];
      var tahun = new Date().getFullYear();
      
      // Hitung tanggal mulai dan akhir bulan
      var tanggalMulai = new Date(tahun, bulanAngka - 1, 1);
      var tanggalAkhir = new Date(tahun, bulanAngka, 0); // Hari terakhir bulan
      var jumlahHari = tanggalAkhir.getDate();
      
      // Generate array tanggal
      var tanggalArray = [];
      for (var i = 0; i < jumlahHari; i++) {
        var tanggal = new Date(tahun, bulanAngka - 1, i + 1);
        tanggalArray.push([tanggal]);
      }
      
      // Clear area sebelumnya dan isi tanggal
      sheet.getRange("L6:L").clearContent();
      if (tanggalArray.length > 0) {
        sheet.getRange(6, 12, tanggalArray.length, 1).setValues(tanggalArray);
        
        // Format sebagai tanggal
        sheet.getRange(6, 12, tanggalArray.length, 1)
          .setNumberFormat("dd/mm/yyyy");
      }
      
    } catch (error) {
      SpreadsheetApp.getUi().alert('Error: ' + error.toString());
    }
  }

  // Fungsi untuk trigger otomatis ketika M2 berubah
  function onEdit(e) {
    var range = e.range;
    var sheet = range.getSheet();
    
    // Jika yang diedit adalah M2
    if (range.getA1Notation() === "M2") {
      generateTanggalBulan();
    }
  }

// Fungsi utama yang dijalankan saat tombol diklik
function getData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const reportSheet = ss.getSheetByName("REPORT");
  
  try {
    // Ambil parameter filter
    const bulanInput = reportSheet.getRange("Q2").getValue().toString().trim();
    const tahun = parseInt(reportSheet.getRange("Q3").getValue());
    const jenisLaporan = reportSheet.getRange("T2").getValue().toString().toLowerCase();
    const ownedBy = reportSheet.getRange("T3").getValue();
    
    // Validasi input
    if (!bulanInput || isNaN(tahun)) {
      SpreadsheetApp.getUi().alert("Error: Mohon isi bulan dan tahun dengan benar!");
      return;
    }
    
    // Konversi nama bulan ke angka (1-12)
    const bulan = convertMonthNameToNumber(bulanInput);
    if (bulan === 0) {
      SpreadsheetApp.getUi().alert("Error: Format bulan tidak valid! Gunakan nama bulan (Januari, Februari, dll)");
      return;
    }
    
    // Kosongkan data lama
    clearOldData(reportSheet);
    
    let resultData = [];
    
    // Proses berdasarkan jenis laporan
    if (jenisLaporan.includes("penjualan")) {
      resultData = getSellingData(ss, bulan, tahun, ownedBy);
      displaySellingResults(reportSheet, resultData);
    } else if (jenisLaporan.includes("pembelian")) {
      resultData = getPurchaseData(ss, bulan, tahun, ownedBy);
      displayPurchaseResults(reportSheet, resultData);
    } else {
      SpreadsheetApp.getUi().alert("Error: Jenis laporan tidak valid! Gunakan 'Penjualan' atau 'Pembelian'");
      return;
    }
    
    // Tampilkan notifikasi
    const message = resultData.length > 0 
      ? `✅ Data berhasil diambil!\n${resultData.length} record ditemukan.`
      : "ℹ️ Tidak ada data yang ditemukan dengan kriteria filter tersebut.";
    
    SpreadsheetApp.getUi().alert(message);
    
  } catch (error) {
    SpreadsheetApp.getUi().alert(`Error: ${error.toString()}`);
    console.error(error);
  }
}

/// Fungsi utama yang dijalankan saat tombol diklik
function getData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const reportSheet = ss.getSheetByName("REPORT");
  
  try {
    // Ambil parameter filter
    const bulanInput = reportSheet.getRange("Q2").getValue().toString().trim();
    const tahun = parseInt(reportSheet.getRange("Q3").getValue());
    const jenisLaporan = reportSheet.getRange("T2").getValue().toString().toLowerCase();
    const ownedBy = reportSheet.getRange("T3").getValue();
    
    // Validasi input
    if (!bulanInput || isNaN(tahun)) {
      SpreadsheetApp.getUi().alert("Error: Mohon isi bulan dan tahun dengan benar!");
      return;
    }
    
    // Konversi nama bulan ke angka (1-12)
    const bulan = convertMonthNameToNumber(bulanInput);
    if (bulan === 0) {
      SpreadsheetApp.getUi().alert("Error: Format bulan tidak valid! Gunakan nama bulan (Januari, Februari, dll)");
      return;
    }
    
    // Kosongkan data lama
    clearOldData(reportSheet);
    
    let resultData = [];
    
    // Proses berdasarkan jenis laporan
    if (jenisLaporan.includes("penjualan")) {
      resultData = getSellingData(ss, bulan, tahun, ownedBy);
      displaySellingResults(reportSheet, resultData);
    } else if (jenisLaporan.includes("pembelian")) {
      resultData = getPurchaseData(ss, bulan, tahun, ownedBy);
      displayPurchaseResults(reportSheet, resultData);
    } else {
      SpreadsheetApp.getUi().alert("Error: Jenis laporan tidak valid! Gunakan 'Penjualan' atau 'Pembelian'");
      return;
    }
    
    // Tampilkan notifikasi
    const message = resultData.length > 0 
      ? `✅ Data berhasil diambil!\n${resultData.length} record ditemukan.`
      : "ℹ️ Tidak ada data yang ditemukan dengan kriteria filter tersebut.";
    
    SpreadsheetApp.getUi().alert(message);
    
  } catch (error) {
    SpreadsheetApp.getUi().alert(`Error: ${error.toString()}`);
    console.error(error);
  }
}

// Fungsi untuk mendapatkan data Penjualan
function getSellingData(ss, bulan, tahun, ownedBy) {
  const result = [];
  
  // 1. Data dari SELLING CASH
  const cashSheet = ss.getSheetByName("SELLING CASH");
  if (cashSheet) {
    const cashData = cashSheet.getDataRange().getValues();
    
    for (let i = 1; i < cashData.length; i++) {
      const row = cashData[i];
      const tanggal = row[2]; // Kolom C
      const invoice = row[3]; // Kolom D
      const item = row[4]; // Kolom E
      const total = row[8] || 0; // Kolom I
      const tax = row[15]; // Kolom P
      const owned = row[14]; // Kolom O
      
      // Validasi filter
      if (isDateMatch(tanggal, bulan, tahun) && 
          tax == 1 && 
          (ownedBy === "" || ownedBy === owned)) {
        
        result.push({
          tanggal: formatDate(tanggal),
          tanggalFaktur: formatDate(tanggal),
          item: item || "",
          invoice: invoice || "",
          total: total,
          customer: "", // Kosong untuk cash (tidak ada customer)
          source: "CASH"
        });
      }
    }
  }
  
  // 2. Data dari SELLING CREDIT
  const creditSheet = ss.getSheetByName("SELLING CREDIT");
  if (creditSheet) {
    const creditData = creditSheet.getDataRange().getValues();
    
    for (let i = 1; i < creditData.length; i++) {
      const row = creditData[i];
      const tanggal = row[2]; // Kolom C
      const invoice = row[3]; // Kolom D
      const customer = row[4]; // Kolom E - INI UNTUK KOLOM X
      const item = row[5]; // Kolom F
      const total = row[14] || 0; // Kolom O
      const category = row[18]; // Kolom S
      const owned = row[19]; // Kolom T
      
      // Validasi filter
      if (isDateMatch(tanggal, bulan, tahun) && 
          category === "Tire" && 
          (ownedBy === "" || ownedBy === owned)) {
        
        result.push({
          tanggal: formatDate(tanggal),
          tanggalFaktur: formatDate(tanggal),
          item: item || "",
          invoice: invoice || "",
          total: total,
          customer: customer || "", // Untuk kolom X
          source: "CREDIT"
        });
      }
    }
  }
  
  return result;
}

// Fungsi untuk mendapatkan data Pembelian
function getPurchaseData(ss, bulan, tahun, ownedBy) {
  const result = [];
  
  const purchaseSheet = ss.getSheetByName("PURCHASE");
  if (!purchaseSheet) return result;
  
  const purchaseData = purchaseSheet.getDataRange().getValues();
  
  for (let i = 1; i < purchaseData.length; i++) {
    const row = purchaseData[i];
    const tglMasuk = row[2]; // Kolom C: Tanggal barang masuk
    const tglFaktur = row[3]; // Kolom D: tanggal faktur
    const distributor = row[4]; // Kolom E: Nama distributor (INI UNTUK KOLOM X)
    const flag = row[5]; // Kolom F: "1"
    const invoice = row[6]; // Kolom G: nomor invoice
    const owned = row[7]; // Kolom H: Owned by
    const item = row[8]; // Kolom I: Nama Item
    const total = row[13] || 0; // Kolom N: Total
    
    // Validasi filter - filter berdasarkan tanggal faktur
    if (isDateMatch(tglFaktur, bulan, tahun) && 
        flag == 1 && 
        (ownedBy === "" || ownedBy === owned)) {
      
      result.push({
        tanggal: formatDate(tglMasuk), // P7: Tanggal barang masuk (Kolom C)
        tanggalFaktur: formatDate(tglFaktur), // T7: Tanggal faktur (Kolom D)
        item: item || "", // Q7: Nama Item (Kolom I)
        invoice: invoice || "", // S7: No Invoice (Kolom G)
        total: total, // U7: Total (Kolom N)
        distributor: distributor || "", // X7: Nama Distributor (Kolom E)
        source: "PURCHASE"
      });
    }
  }
  
  return result;
}

// Fungsi untuk menampilkan hasil PENJUALAN
function displaySellingResults(sheet, data) {
  if (data.length === 0) return;
  
  const startRow = 7; // Mulai dari row 7
  const startCol = 16; // Kolom P (index 16)
  
  // Siapkan output untuk penjualan
  const output = data.map(item => [
    item.tanggal,                    // Kolom P: Tanggal
    item.item,                       // Kolom Q: Nama Item
    "",                              // Kolom R: (kosong)
    item.invoice,                    // Kolom S: No Invoice
    item.tanggalFaktur,              // Kolom T: Tanggal Faktur
    item.total,                      // Kolom U: Total
    "", "", "",                      // Kolom V, W, X (X akan diisi khusus)
    "",                              // Kolom Y: (kosong)
    ""                               // Kolom Z: KOSONG untuk penjualan (tidak ada duplikasi)
  ]);
  
  // Tulis data utama
  const outputRange = sheet.getRange(startRow, startCol, output.length, output[0].length);
  outputRange.setValues(output);
  
  // Format angka untuk kolom Total (U)
  sheet.getRange(startRow, 21, output.length, 1).setNumberFormat("#,##0");
  
  // ISI KOLOM X dengan Nama Customer (hanya untuk SELLING CREDIT)
  for (let i = 0; i < data.length; i++) {
    if (data[i].source === "CREDIT") {
      sheet.getRange(startRow + i, 24).setValue(data[i].customer); // Kolom X
    }
    // Untuk SELLING CASH, kolom X tetap kosong
  }
  
  // Pastikan kolom Z kosong untuk semua data penjualan
  sheet.getRange(startRow, 26, data.length, 1).clearContent(); // Kolom Z
}

// Fungsi untuk menampilkan hasil PEMBELIAN
function displayPurchaseResults(sheet, data) {
  if (data.length === 0) return;
  
  const startRow = 7; // Mulai dari row 7
  const startCol = 16; // Kolom P (index 16)
  
  // Siapkan output untuk pembelian
  const output = data.map(item => [
    item.tanggal,                    // Kolom P: Tanggal barang masuk (C)
    item.item,                       // Kolom Q: Nama Item (I)
    "",                              // Kolom R: (kosong)
    item.invoice,                    // Kolom S: No Invoice (G)
    item.tanggalFaktur,              // Kolom T: Tanggal faktur (D)
    item.total,                      // Kolom U: Total (N)
    "", "", "",                      // Kolom V, W, X (X akan diisi khusus)
    "",                              // Kolom Y: (kosong)
    ""                               // Kolom Z: (kosong untuk pembelian)
  ]);
  
  // Tulis data utama
  const outputRange = sheet.getRange(startRow, startCol, output.length, output[0].length);
  outputRange.setValues(output);
  
  // Format angka untuk kolom Total (U)
  sheet.getRange(startRow, 21, output.length, 1).setNumberFormat("#,##0");
  
  // ISI KOLOM X dengan Nama Distributor
  for (let i = 0; i < data.length; i++) {
    sheet.getRange(startRow + i, 24).setValue(data[i].distributor); // Kolom X
  }
  
  // Pastikan kolom Z kosong untuk pembelian
  sheet.getRange(startRow, 26, data.length, 1).clearContent(); // Kolom Z
}

// Fungsi untuk membersihkan data lama
function clearOldData(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow >= 7) {
    // Clear dari P7 sampai Z (kolom 16 sampai 26)
    sheet.getRange(7, 16, lastRow - 6, 11).clearContent();
  }
}

// Helper function: Cek apakah tanggal sesuai dengan bulan dan tahun
function isDateMatch(dateValue, bulan, tahun) {
  if (!dateValue) return false;
  
  try {
    const date = new Date(dateValue);
    if (isNaN(date.getTime())) return false;
    
    const dateBulan = date.getMonth() + 1;
    const dateTahun = date.getFullYear();
    
    return dateBulan === bulan && dateTahun === tahun;
  } catch (e) {
    return false;
  }
}

// Helper function: Format tanggal ke string
function formatDate(dateValue) {
  if (!dateValue) return "";
  
  try {
    const date = new Date(dateValue);
    if (isNaN(date.getTime())) return dateValue.toString();
    
    return Utilities.formatDate(date, Session.getScriptTimeZone(), "dd/MM/yyyy");
  } catch (e) {
    return dateValue.toString();
  }
}

// Helper function: Konversi nama bulan ke angka
function convertMonthNameToNumber(monthName) {
  const months = {
    'januari': 1, 'februari': 2, 'maret': 3, 'april': 4,
    'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8,
    'september': 9, 'oktober': 10, 'november': 11, 'desember': 12,
    'january': 1, 'february': 2, 'march': 3, 'may': 5,
    'june': 6, 'july': 7, 'august': 8, 'october': 10,
    'december': 12
  };
  
  return months[monthName.toLowerCase()] || 0;
}

// Fungsi untuk membuat tombol menu
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('📊 Laporan Custom')
    .addItem('▶️ Get Data', 'getData')
    .addItem('🔄 Clear Data', 'clearOldDataFromMenu')
    .addToUi();
}

// Fungsi untuk clear data dari menu
function clearOldDataFromMenu() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const reportSheet = ss.getSheetByName("REPORT");
  clearOldData(reportSheet);
  SpreadsheetApp.getUi().alert("✅ Data berhasil dibersihkan!");
}